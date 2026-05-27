"""Bot runtime configuration — env loading + defaults.

Phase 2 reads a single bootstrap ``TELEGRAM_BOT_TOKEN`` plus the
service-account Dograh API key. Phase 4 will replace these with
per-channel records loaded from ``im_channels`` via the IM-channels
secret-bundle endpoint (see ADR-102).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v if v is not None and v != "" else default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw not in (None, "") else default
    except ValueError:
        return default


def _env_csv_ints(name: str) -> list[int]:
    raw = os.getenv(name, "")
    out: list[int] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            out.append(int(piece))
        except ValueError:
            continue
    return out


@dataclass(frozen=True)
class BotConfig:
    # Dograh API
    dograh_api_url: str
    dograh_api_key: str  # X-API-Key header value (ADR-102)

    # Telegram (bootstrap; Phase 4 replaces with DB-loaded channels)
    telegram_bot_token: str
    telegram_allowed_users: list[int]

    # Postgres + Redis (shared with the api)
    database_url: str
    redis_url: str

    # Optional integrations
    groq_api_key: str  # voice-note STT (Phase 3)

    # Healthcheck
    health_port: int


def load_config() -> BotConfig:
    return BotConfig(
        dograh_api_url=_env("DOGRAH_API_URL", "http://api:8000"),
        dograh_api_key=_env("DOGRAH_API_KEY", ""),
        telegram_bot_token=_env("TELEGRAM_BOT_TOKEN", ""),
        telegram_allowed_users=_env_csv_ints("TELEGRAM_ALLOWED_USERS"),
        database_url=_env("DATABASE_URL", ""),
        redis_url=_env("REDIS_URL", ""),
        groq_api_key=_env("GROQ_API_KEY", ""),
        health_port=_env_int("TELEGRAM_BOT_HEALTH_PORT", 8080),
    )
