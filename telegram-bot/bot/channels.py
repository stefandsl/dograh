"""IM channels loader + hot-reload manager.

Pulls the secret bundle from the api at boot, spins up one aiogram
``Bot + Dispatcher`` per enabled Telegram channel, and subscribes to
the Redis ``im:channels:reload`` channel to react to admin changes
without a restart.

The Router tree is shared across all bots — each dispatcher just gets
its own copy of the router include and its own per-bot context kwargs
(notably ``cfg`` for the allowlist).

On a reload event we diff loaded vs incoming:
- new ids → start polling
- removed ids → stop polling + close
- changed config (token / allowlist) → stop + start (cheaper than
  trying to mutate aiogram state in-place)
"""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

import httpx
import redis.asyncio as aioredis
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger


RELOAD_CHANNEL = "im:channels:reload"


@dataclass
class ChannelBundle:
    id: int
    organization_id: int
    name: str
    bot_token: str
    api_key: str
    allowed_user_ids: list[int]

    def key(self) -> tuple:
        """Treat (token, sorted allowed list, name) as the diff key."""
        return (
            self.bot_token,
            tuple(sorted(self.allowed_user_ids)),
            self.name,
        )


@dataclass
class _RunningBot:
    bundle: ChannelBundle
    bot: Bot
    dispatcher: Dispatcher
    task: asyncio.Task[None]


class TelegramChannelManager:
    """Owns the set of running aiogram dispatchers, one per channel."""

    def __init__(
        self,
        *,
        dograh_api_url: str,
        internal_secret: str,
        redis_url: str,
        router_factory: Callable[[], Any],
        handler_kwargs_factory: Callable[[ChannelBundle], dict[str, Any]],
        middleware_factory: Optional[
            Callable[[ChannelBundle], list[Any]]
        ] = None,
    ) -> None:
        self._api_url = dograh_api_url.rstrip("/")
        self._secret = internal_secret
        self._redis_url = redis_url
        self._router_factory = router_factory
        self._handler_kwargs_factory = handler_kwargs_factory
        self._middleware_factory = middleware_factory or (lambda _b: [])

        self._bots: dict[int, _RunningBot] = {}
        self._reload_task: Optional[asyncio.Task[None]] = None
        self._stop = asyncio.Event()

    # --- lifecycle ----------------------------------------------------
    async def start(self) -> None:
        await self.reload()
        self._reload_task = asyncio.create_task(
            self._listen_for_reloads(), name="im-channels-reload-listener"
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._reload_task is not None:
            self._reload_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._reload_task
        for rb in list(self._bots.values()):
            await self._stop_bot(rb)
        self._bots.clear()

    # --- bundle fetch -------------------------------------------------
    async def _fetch_bundles(self) -> list[ChannelBundle]:
        if not self._secret:
            logger.warning(
                "[channels] IM_INTERNAL_SECRET not set; refusing to fetch "
                "secret bundle (no bots will run)"
            )
            return []
        url = f"{self._api_url}/api/v1/im/channels/secret-bundle"
        try:
            async with httpx.AsyncClient(timeout=15.0) as c:
                r = await c.get(
                    url, headers={"X-IM-Internal-Secret": self._secret}
                )
            if r.status_code != 200:
                logger.warning(
                    f"[channels] secret-bundle returned {r.status_code}: "
                    f"{r.text[:200]}"
                )
                return []
            return [ChannelBundle(**b) for b in r.json()]
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[channels] failed to fetch bundle: {exc!r}")
            return []

    # --- reload diff --------------------------------------------------
    async def reload(self) -> None:
        bundles = await self._fetch_bundles()
        by_id = {b.id: b for b in bundles}

        # Stop bots that disappeared OR changed config.
        for cid in list(self._bots.keys()):
            running = self._bots[cid]
            incoming = by_id.get(cid)
            if incoming is None or incoming.key() != running.bundle.key():
                logger.info(
                    f"[channels] stopping bot for channel id={cid} "
                    f"({'removed' if incoming is None else 'config-changed'})"
                )
                await self._stop_bot(running)
                del self._bots[cid]

        # Start any new (or restart-needed) channels.
        for cid, bundle in by_id.items():
            if cid in self._bots:
                continue
            await self._start_bot(bundle)

        logger.info(
            f"[channels] reload done — {len(self._bots)} bot(s) running"
        )

    async def _start_bot(self, bundle: ChannelBundle) -> None:
        if not bundle.bot_token:
            logger.warning(
                f"[channels] channel {bundle.id} ({bundle.name}) has no "
                f"bot_token; skipping"
            )
            return
        bot = Bot(
            token=bundle.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        try:
            me = await bot.get_me()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"[channels] getMe failed for channel {bundle.id} "
                f"({bundle.name}): {exc!r}"
            )
            await bot.session.close()
            return
        dp = Dispatcher()
        for mw in self._middleware_factory(bundle):
            dp.update.outer_middleware(mw)
        dp.include_router(self._router_factory())
        kwargs = self._handler_kwargs_factory(bundle)
        task = asyncio.create_task(
            dp.start_polling(bot, **kwargs),
            name=f"aiogram-polling-{bundle.id}",
        )
        self._bots[bundle.id] = _RunningBot(
            bundle=bundle, bot=bot, dispatcher=dp, task=task
        )
        logger.info(
            f"[channels] started channel {bundle.id} ({bundle.name}) as "
            f"@{me.username}"
        )

    async def _stop_bot(self, rb: _RunningBot) -> None:
        rb.task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await rb.task
        with suppress(Exception):
            await rb.bot.session.close()

    # --- redis subscriber --------------------------------------------
    async def _listen_for_reloads(self) -> None:
        if not self._redis_url:
            logger.warning(
                "[channels] REDIS_URL not set; hot-reload disabled"
            )
            await self._stop.wait()
            return

        backoff = 1.0
        while not self._stop.is_set():
            try:
                r = aioredis.from_url(self._redis_url)
                async with r.pubsub() as pubsub:
                    await pubsub.subscribe(RELOAD_CHANNEL)
                    logger.info(
                        f"[channels] subscribed to redis '{RELOAD_CHANNEL}'"
                    )
                    backoff = 1.0
                    async for msg in pubsub.listen():
                        if self._stop.is_set():
                            break
                        if msg.get("type") != "message":
                            continue
                        logger.info(
                            "[channels] reload event received, "
                            "re-pulling bundle"
                        )
                        await self.reload()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"[channels] redis subscriber error ({exc!r}); "
                    f"reconnecting in {backoff:.1f}s"
                )
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, 30.0)


def get_internal_secret() -> str:
    return os.getenv("IM_INTERNAL_SECRET", "")
