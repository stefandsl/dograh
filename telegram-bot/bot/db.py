"""Postgres connection helper for the Telegram bot.

Uses the same DATABASE_URL the Dograh api uses (asyncpg driver under
sqlalchemy 2.x). Per ADR-103 the bot owns three tables —
``telegram_memory_facts``, ``telegram_sessions``,
``telegram_scheduled_tasks`` — all created in the
``a4b5c6d7e8f9_telegram_im_tables`` migration that ships with the
api's Alembic timeline.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


_engine: Optional[AsyncEngine] = None
_Session: Optional[async_sessionmaker[AsyncSession]] = None


def init_engine(database_url: str) -> None:
    """Build the singleton engine. Call once at startup."""
    global _engine, _Session
    if not database_url:
        # Sometimes the bot runs without DB access (e.g. healthcheck-only
        # in CI) — let lazy lookups fail loud later.
        return
    _engine = create_async_engine(database_url, pool_pre_ping=True)
    _Session = async_sessionmaker(_engine, expire_on_commit=False)


def session_factory() -> async_sessionmaker[AsyncSession]:
    if _Session is None:
        raise RuntimeError(
            "telegram-bot DB not initialised — call init_engine(...) first"
        )
    return _Session


async def dispose() -> None:
    global _engine, _Session
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _Session = None
