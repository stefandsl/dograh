"""Telegram bot entrypoint.

Two modes:

1. **Bootstrap mode** — if ``TELEGRAM_BOT_TOKEN`` is set in env, run a
   single dispatcher using that token + the env allowlist. This is the
   Phase 1/2/3 behaviour and stays as the fallback for dev where the
   api isn't reachable.

2. **Multi-channel mode** — if ``IM_INTERNAL_SECRET`` is set, fetch the
   ``/api/v1/im/channels/secret-bundle`` payload from the api and run
   one dispatcher per enabled Telegram channel. Hot-reloads on the
   Redis ``im:channels:reload`` event.

If both env vars are present, multi-channel mode wins (it carries
allowlists per-channel) and the bootstrap token is ignored.

The handler router is the single ``router`` object below; both modes
include it into their dispatcher(s).
"""

from __future__ import annotations

import asyncio
import os
import signal
from contextlib import suppress
from typing import Any, Awaitable, Callable

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
    WebAppInfo,
)
from aiohttp import web
from loguru import logger

from .channels import (
    ChannelBundle,
    TelegramChannelManager,
    get_internal_secret,
)
from .config import BotConfig, load_config
from .db import dispose as db_dispose, init_engine
from .dograh_client import DograhClient, DograhClientError
from .formatting import md_to_telegram_html
from .handlers import build_menu_router
from .menu import build_main_menu
from .voice import transcribe_voice


# --- middleware -----------------------------------------------------------
class AllowedUsersMiddleware:
    """Drop updates from users not on the allowlist (empty list = allow all)."""

    def __init__(self, allowed: list[int]) -> None:
        self._allowed = set(allowed)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not self._allowed:
            return await handler(event, data)
        user = data.get("event_from_user")
        if user is not None and user.id in self._allowed:
            return await handler(event, data)
        logger.warning(
            f"[telegram-bot] dropping update from non-allowed user "
            f"id={getattr(user, 'id', None)}"
        )
        return None


# --- handlers (shared across every bot) ----------------------------------
def build_router() -> Router:
    """Build a fresh Router so each Dispatcher gets its own include tree."""
    r = Router(name="dograh-telegram-bot")

    @r.message(Command("start"))
    async def on_start(message: Message) -> None:
        await message.answer(
            "<b>Dograh bot online.</b>\n\nPick an action:",
            reply_markup=build_main_menu(),
        )

    @r.message(Command("help"))
    async def on_help(message: Message) -> None:
        await on_start(message)

    @r.message(Command("workflows"))
    async def on_workflows(message: Message, dograh: DograhClient) -> None:
        try:
            workflows = await dograh.list_workflows_summary()
        except DograhClientError as exc:
            await message.answer(f"❌ Dograh API error: {exc}")
            return
        if not workflows:
            await message.answer(
                "No workflows yet. Create one in the Dograh UI first."
            )
            return
        lines = ["<b>Available workflows</b>"]
        for w in workflows[:25]:
            wid = w.get("id") or w.get("workflow_id")
            name = w.get("name") or "(untitled)"
            lines.append(f"• <code>{wid}</code> — {name}")
        await message.answer("\n".join(lines))

    @r.message(Command("call"))
    async def on_call(message: Message, dograh: DograhClient) -> None:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip().isdigit():
            await message.answer("Usage: <code>/call &lt;workflow_id&gt;</code>")
            return
        workflow_id = int(parts[1].strip())
        chat_id = message.chat.id
        try:
            link = await dograh.request_web_call_link(
                workflow_id=workflow_id, telegram_chat_id=chat_id
            )
        except DograhClientError as exc:
            await message.answer(f"❌ Dograh API error: {exc}")
            return
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="🎙️ Open Voice Call",
                    web_app=WebAppInfo(url=link["url"]),
                )
            ]]
        )
        await message.answer(
            f"Tap to start a voice call (link valid {link['expires_in_seconds']}s):",
            reply_markup=kb,
        )

    @r.message(lambda m: m.voice is not None)
    async def on_voice(
        message: Message, bot: Bot, dograh: DograhClient, cfg: BotConfig
    ) -> None:
        if message.voice is None:
            return
        transcript = await transcribe_voice(
            message.voice, bot, cfg.groq_api_key
        )
        if transcript is None:
            await message.answer(
                "🎙️ Got your voice note, but Groq Whisper isn't configured "
                "(set <code>GROQ_API_KEY</code>)."
            )
            return
        if transcript.startswith("[STT error"):
            await message.answer(f"🎙️ {transcript}")
            return
        await message.answer(
            md_to_telegram_html(
                f"🎙️ *Transcript:*\n{transcript}\n\n"
                "_Phase 5 will route this into your active workflow._"
            )
        )

    @r.message()
    async def on_text(message: Message) -> None:
        # Fallback for text outside chat mode (handlers.py owns the
        # ChatStates.chatting branch). Nudge toward the menu.
        if not message.text:
            return
        await message.answer(
            "📝 Not in chat mode. Open <b>💬 Chat with Agent</b> from /menu "
            "to start a workflow conversation."
        )

    # Mount the Syntx-style menu router under this bot's router tree.
    r.include_router(build_menu_router())
    return r


# --- runner ---------------------------------------------------------------
async def _build_health_app() -> web.Application:
    app = web.Application()
    app.router.add_get(
        "/healthz",
        lambda _: web.json_response(
            {"status": "ok", "service": "telegram-bot"}
        ),
    )
    return app


async def _start_health_server(port: int) -> web.AppRunner:
    runner = web.AppRunner(await _build_health_app())
    await runner.setup()
    await web.TCPSite(runner, host="0.0.0.0", port=port).start()
    logger.info(f"[telegram-bot] health server listening on :{port}")
    return runner


async def _run_bootstrap_dispatcher(cfg: BotConfig) -> asyncio.Task[None] | None:
    """Old single-token path — kept as a fallback when no IM_INTERNAL_SECRET."""
    if not cfg.telegram_bot_token:
        logger.warning(
            "[telegram-bot] TELEGRAM_BOT_TOKEN not set and IM_INTERNAL_SECRET "
            "not set either — running health-only"
        )
        return None
    bot = Bot(
        token=cfg.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.update.outer_middleware(
        AllowedUsersMiddleware(cfg.telegram_allowed_users)
    )
    dp.include_router(build_router())
    dograh_cm = DograhClient(
        base_url=cfg.dograh_api_url, api_key=cfg.dograh_api_key
    )
    await dograh_cm.__aenter__()
    try:
        me = await bot.get_me()
        logger.info(
            f"[telegram-bot] bootstrap bot online as @{me.username} "
            f"(id={me.id})"
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[telegram-bot] bootstrap getMe failed: {exc!r}")
        await dograh_cm.__aexit__()
        return None
    return asyncio.create_task(
        dp.start_polling(bot, dograh=dograh_cm, cfg=cfg),
        name="aiogram-bootstrap-polling",
    )


def _make_multi_channel_kwargs(cfg: BotConfig) -> Callable[[ChannelBundle], dict[str, Any]]:
    """Per-bot context kwargs for multi-channel mode."""
    def factory(bundle: ChannelBundle) -> dict[str, Any]:
        # One DograhClient per bot — the per-channel api_key from the
        # bundle, NOT the env DOGRAH_API_KEY. Lifetime is tied to the
        # dispatcher task; we leak the __aenter__ on purpose, the
        # channel manager closes the bot session when removing.
        dograh = DograhClient(
            base_url=cfg.dograh_api_url, api_key=bundle.api_key
        )
        return {
            "dograh": _LazyEnteredClient(dograh),
            "cfg": cfg,
        }
    return factory


class _LazyEnteredClient:
    """Wraps a DograhClient so first use opens the httpx session.

    Avoids juggling __aenter__/__aexit__ across dispatcher lifetimes.
    """

    def __init__(self, client: DograhClient):
        self._client = client
        self._entered = False
        self._lock = asyncio.Lock()

    async def __aenter__(self):  # pragma: no cover (not used as ctx mgr)
        return self

    def __getattr__(self, name):
        async def _wrapper(*args, **kwargs):
            async with self._lock:
                if not self._entered:
                    await self._client.__aenter__()
                    self._entered = True
            return await getattr(self._client, name)(*args, **kwargs)
        return _wrapper


async def _run(cfg: BotConfig) -> None:
    init_engine(cfg.database_url)
    health_runner = await _start_health_server(cfg.health_port)

    manager: TelegramChannelManager | None = None
    bootstrap_task: asyncio.Task[None] | None = None

    internal_secret = get_internal_secret()
    if internal_secret:
        manager = TelegramChannelManager(
            dograh_api_url=cfg.dograh_api_url,
            internal_secret=internal_secret,
            redis_url=cfg.redis_url,
            router_factory=build_router,
            handler_kwargs_factory=_make_multi_channel_kwargs(cfg),
            middleware_factory=lambda bundle: [
                AllowedUsersMiddleware(bundle.allowed_user_ids)
            ],
        )
        await manager.start()
        logger.info("[telegram-bot] multi-channel mode online")
    else:
        bootstrap_task = await _run_bootstrap_dispatcher(cfg)

    stop = asyncio.Event()

    def _signal_stop(signame: str) -> None:
        logger.info(f"[telegram-bot] received {signame}, shutting down")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_stop, sig.name)

    try:
        await stop.wait()
    finally:
        if manager is not None:
            await manager.stop()
        if bootstrap_task is not None:
            bootstrap_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await bootstrap_task
        await health_runner.cleanup()
        await db_dispose()
        logger.info("[telegram-bot] stopped")


def main() -> None:
    cfg = load_config()
    asyncio.run(_run(cfg))


if __name__ == "__main__":
    main()
