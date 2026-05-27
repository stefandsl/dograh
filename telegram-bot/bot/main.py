"""Telegram bot entrypoint.

Phase 2 scope: aiohttp health server (Phase 1) + aiogram Dispatcher
running side-by-side, with the bootstrap ``TELEGRAM_BOT_TOKEN`` from
env. Three handlers wired:

- ``/start``       — greet + show how to pick a workflow
- ``/workflows``   — list workflows (calls Dograh API)
- text message     — placeholder reply (Phase 5 will wire it into the
                     active workflow run)

Phase 4 will replace the single-token bootstrap with per-channel tokens
loaded from the ``im_channels`` table. Phase 5 expands the handler set
into the Syntx-style inline menu.

Allowed-user gate (``TELEGRAM_ALLOWED_USERS`` csv) is applied as an
outer middleware so every handler benefits automatically.
"""

from __future__ import annotations

import asyncio
import signal
from contextlib import suppress
from typing import Any, Awaitable, Callable

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, TelegramObject
from aiohttp import web
from loguru import logger

from .config import BotConfig, load_config
from .db import dispose as db_dispose, init_engine
from .dograh_client import DograhClient, DograhClientError
from .formatting import md_to_telegram_html


router = Router(name="dograh-telegram-bot")


# --- middleware -----------------------------------------------------------
class AllowedUsersMiddleware:
    """Drop updates from users not on the allowlist (empty list = allow all).

    aiogram 3 outer-middleware signature: ``async def __call__(handler, event, data)``.
    """

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


# --- handlers -------------------------------------------------------------
@router.message(Command("start"))
async def on_start(message: Message) -> None:
    await message.answer(
        md_to_telegram_html(
            "*Dograh bot online.*\n\n"
            "Quick start:\n"
            "• `/workflows` — list available workflows\n"
            "• send any text — placeholder echo for now (full chat lands in Phase 5)\n"
        )
    )


@router.message(Command("help"))
async def on_help(message: Message) -> None:
    await on_start(message)


@router.message(Command("workflows"))
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


@router.message()
async def on_text(message: Message) -> None:
    # Phase 2 placeholder: prove the dispatcher is alive and the
    # /workflows handler isn't the only handler. Phase 5 replaces this
    # with the chat-with-active-workflow flow.
    if not message.text:
        return
    await message.answer(
        "📝 received — Phase 5 will route this to your active workflow."
    )


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


async def _run(cfg: BotConfig) -> None:
    init_engine(cfg.database_url)
    health_runner = await _start_health_server(cfg.health_port)

    bot_task: asyncio.Task[None] | None = None
    if cfg.telegram_bot_token:
        bot = Bot(
            token=cfg.telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dp = Dispatcher()
        dp.update.outer_middleware(
            AllowedUsersMiddleware(cfg.telegram_allowed_users)
        )
        dp.include_router(router)

        # Inject a long-lived DograhClient into every handler context.
        dograh_cm = DograhClient(
            base_url=cfg.dograh_api_url, api_key=cfg.dograh_api_key
        )
        await dograh_cm.__aenter__()
        try:
            me = await bot.get_me()
            logger.info(
                f"[telegram-bot] bot online as @{me.username} (id={me.id})"
            )
            bot_task = asyncio.create_task(
                dp.start_polling(bot, dograh=dograh_cm),
                name="aiogram-polling",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"[telegram-bot] failed to start polling: {exc!r}")
    else:
        logger.warning(
            "[telegram-bot] TELEGRAM_BOT_TOKEN not set — running health-only "
            "(Phase 4 will load tokens from the im_channels table)"
        )

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
        if bot_task is not None:
            bot_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await bot_task
        await health_runner.cleanup()
        await db_dispose()
        logger.info("[telegram-bot] stopped")


def main() -> None:
    cfg = load_config()
    asyncio.run(_run(cfg))


if __name__ == "__main__":
    main()
