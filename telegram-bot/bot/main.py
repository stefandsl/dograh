"""Telegram bot entrypoint.

Phase 1 scope (this file): start an aiohttp health server on :8080 so
the docker healthcheck and the api-side IM-channels watcher have
something to probe. Subsequent phases bolt on the aiogram dispatcher,
multi-token loader (Phase 4), and handlers (Phase 5).

Keeping this minimal on purpose — Phase 1's verifier is "container
builds and the healthcheck flips to healthy", not "bot is functional".
"""

from __future__ import annotations

import asyncio
import os
import signal

from aiohttp import web
from loguru import logger


HEALTH_PORT = int(os.getenv("TELEGRAM_BOT_HEALTH_PORT", "8080"))


async def _healthz(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "telegram-bot"})


async def _build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/healthz", _healthz)
    return app


async def _serve() -> None:
    app = await _build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=HEALTH_PORT)
    await site.start()
    logger.info(f"[telegram-bot] health server listening on :{HEALTH_PORT}")

    # Park forever until SIGTERM/SIGINT.
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
        await runner.cleanup()
        logger.info("[telegram-bot] stopped")


def main() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
