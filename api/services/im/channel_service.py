"""IM channel CRUD service.

Encryption layer + Redis pub/sub for hot-reload + service-account API
key auto-minting. The HTTP router lives in ``api/routes/im_channels.py``
and stays thin — it parses, calls these helpers, shapes responses.

Per ADR-102 every IM channel has an associated service-account API key
in the same org. The bot loads ``(bot_token, api_key)`` pairs via the
``secret-bundle`` route on boot and on each Redis ``im:channels:reload``
event.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

import httpx
import redis.asyncio as aioredis
from loguru import logger
from sqlalchemy import select

from api.constants import REDIS_URL
from api.db import db_client
from api.db.models import ImChannelModel

from .encryption import fernet

RELOAD_CHANNEL = "im:channels:reload"


# --- encryption -----------------------------------------------------------
def encrypt_config(payload: dict[str, Any]) -> str:
    return fernet.encrypt(json.dumps(payload, separators=(",", ":")).encode()).decode()


def decrypt_config(ciphertext: str) -> dict[str, Any]:
    raw = fernet.decrypt(ciphertext.encode())
    return json.loads(raw)


# --- DTOs -----------------------------------------------------------------
@dataclass
class ImChannelRecord:
    """Plain dict-like view of a row + decrypted config (no secrets in repr)."""

    id: int
    organization_id: int
    type: str
    name: str
    enabled: bool
    api_key_id: Optional[int]
    config: dict[str, Any]

    def to_public_dict(self) -> dict[str, Any]:
        """UI-safe shape — masks every per-channel secret to last 6 chars."""
        cfg = dict(self.config)
        for secret_field in (
            "bot_token",  # telegram
            "access_token",  # whatsapp meta cloud api
            "app_secret",  # whatsapp meta cloud api
            "verify_token",  # whatsapp meta cloud api
            "api_key",  # service-account key (shared across types)
        ):
            value = cfg.get(secret_field)
            if isinstance(value, str) and value:
                cfg[secret_field] = "***" + value[-6:]
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "type": self.type,
            "name": self.name,
            "enabled": self.enabled,
            "api_key_id": self.api_key_id,
            "config": cfg,
        }


# --- queries --------------------------------------------------------------
async def list_channels(
    *, organization_id: int, type_filter: Optional[str] = None
) -> list[ImChannelRecord]:
    async with db_client.async_session() as s:
        stmt = select(ImChannelModel).where(
            ImChannelModel.organization_id == organization_id
        )
        if type_filter:
            stmt = stmt.where(ImChannelModel.type == type_filter)
        result = await s.execute(stmt)
        rows = result.scalars().all()
    return [_row_to_record(row) for row in rows]


async def get_channel(
    *, organization_id: int, channel_id: int
) -> Optional[ImChannelRecord]:
    async with db_client.async_session() as s:
        result = await s.execute(
            select(ImChannelModel).where(
                ImChannelModel.id == channel_id,
                ImChannelModel.organization_id == organization_id,
            )
        )
        row = result.scalars().first()
    return _row_to_record(row) if row else None


async def get_channel_by_id_unscoped(channel_id: int) -> Optional[ImChannelRecord]:
    """Fetch a channel without org scoping.

    Used only by public webhook endpoints (WhatsApp Meta verify + receive)
    where the channel_id is in the URL path and access control is provided
    by the channel's own verify_token / app_secret rather than a user
    session. Never call this from authenticated routes — use
    ``get_channel`` instead.
    """
    async with db_client.async_session() as s:
        result = await s.execute(
            select(ImChannelModel).where(ImChannelModel.id == channel_id)
        )
        row = result.scalars().first()
    return _row_to_record(row) if row else None


def _row_to_record(row: ImChannelModel) -> ImChannelRecord:
    return ImChannelRecord(
        id=row.id,
        organization_id=row.organization_id,
        type=row.type,
        name=row.name,
        enabled=row.enabled,
        api_key_id=row.api_key_id,
        config=decrypt_config(row.config_encrypted),
    )


# --- create / update / delete --------------------------------------------
async def create_telegram_channel(
    *,
    organization_id: int,
    user_id: Optional[int],
    name: str,
    bot_token: str,
    allowed_user_ids: list[int],
    enabled: bool = True,
) -> tuple[ImChannelRecord, str]:
    """Create a Telegram channel + auto-mint a service-account API key.

    Returns ``(record, raw_api_key)``. The raw key is shown to the
    operator only at creation time and ALSO written into the encrypted
    config blob so the bot can fetch both with a single secret-bundle
    call later (ADR-102).
    """
    api_key, raw_api_key = await db_client.create_api_key(
        organization_id=organization_id,
        name=f"im/telegram/{name}",
        created_by=user_id,
    )
    config = {
        "bot_token": bot_token,
        "allowed_user_ids": list(allowed_user_ids),
        # Plaintext key kept inside the encrypted blob — see ADR-102.
        "api_key": raw_api_key,
    }
    async with db_client.async_session() as s:
        row = ImChannelModel(
            organization_id=organization_id,
            type="telegram",
            name=name,
            config_encrypted=encrypt_config(config),
            enabled=enabled,
            api_key_id=api_key.id,
            created_by=user_id,
        )
        s.add(row)
        await s.commit()
        await s.refresh(row)
    await publish_reload()
    return _row_to_record(row), raw_api_key


async def update_telegram_channel(
    *,
    organization_id: int,
    channel_id: int,
    enabled: Optional[bool] = None,
    allowed_user_ids: Optional[list[int]] = None,
    bot_token: Optional[str] = None,
    name: Optional[str] = None,
) -> Optional[ImChannelRecord]:
    async with db_client.async_session() as s:
        result = await s.execute(
            select(ImChannelModel).where(
                ImChannelModel.id == channel_id,
                ImChannelModel.organization_id == organization_id,
            )
        )
        row = result.scalars().first()
        if row is None:
            return None
        config = decrypt_config(row.config_encrypted)
        if bot_token is not None:
            config["bot_token"] = bot_token
        if allowed_user_ids is not None:
            config["allowed_user_ids"] = list(allowed_user_ids)
        if name is not None:
            row.name = name
        if enabled is not None:
            row.enabled = enabled
        row.config_encrypted = encrypt_config(config)
        await s.commit()
        await s.refresh(row)
    await publish_reload()
    return _row_to_record(row)


async def delete_channel(*, organization_id: int, channel_id: int) -> bool:
    async with db_client.async_session() as s:
        result = await s.execute(
            select(ImChannelModel).where(
                ImChannelModel.id == channel_id,
                ImChannelModel.organization_id == organization_id,
            )
        )
        row = result.scalars().first()
        if row is None:
            return False
        await s.delete(row)
        await s.commit()
    await publish_reload()
    return True


async def rotate_api_key(
    *, organization_id: int, channel_id: int, user_id: Optional[int]
) -> Optional[tuple[ImChannelRecord, str]]:
    """Mint a fresh API key, swap the channel's link, return new raw key."""
    async with db_client.async_session() as s:
        result = await s.execute(
            select(ImChannelModel).where(
                ImChannelModel.id == channel_id,
                ImChannelModel.organization_id == organization_id,
            )
        )
        row = result.scalars().first()
        if row is None:
            return None
        new_key, raw = await db_client.create_api_key(
            organization_id=organization_id,
            name=f"im/{row.type}/{row.name}",
            created_by=user_id,
        )
        config = decrypt_config(row.config_encrypted)
        config["api_key"] = raw
        row.config_encrypted = encrypt_config(config)
        row.api_key_id = new_key.id
        await s.commit()
        await s.refresh(row)
    await publish_reload()
    return _row_to_record(row), raw


# --- test connection (calls Telegram getMe) -------------------------------
async def test_telegram_token(bot_token: str) -> dict[str, Any]:
    """Hit Telegram's ``/getMe``; return ``{ok, username?, error?}``."""
    if not bot_token:
        return {"ok": False, "error": "empty bot token"}
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            resp = await c.get(url)
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        body = resp.json()
        if not body.get("ok"):
            return {"ok": False, "error": str(body.get("description", "rejected"))}
        result = body.get("result", {})
        return {
            "ok": True,
            "username": result.get("username"),
            "bot_id": result.get("id"),
            "first_name": result.get("first_name"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# --- reload pub/sub -------------------------------------------------------
async def publish_reload() -> None:
    """Notify the bot container to re-pull the secret bundle."""
    try:
        r = aioredis.from_url(REDIS_URL)
        try:
            await r.publish(RELOAD_CHANNEL, "1")
        finally:
            await r.aclose()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[im/channel_service] Redis publish failed: {exc!r}")


# --- whatsapp -------------------------------------------------------------
# WhatsApp Cloud API receives messages via HTTP webhooks (not long-polling
# like Telegram), so there is no separate bot container and no service-
# account API key auto-mint here — the webhook handler lives inside the
# api container and looks up the channel row directly. The encrypted
# config stores only Meta credentials.
async def create_whatsapp_channel(
    *,
    organization_id: int,
    user_id: Optional[int],
    name: str,
    phone_number_id: str,
    access_token: str,
    app_secret: str,
    verify_token: str,
    business_account_id: Optional[str] = None,
    graph_version: str = "v20.0",
    enabled: bool = True,
) -> ImChannelRecord:
    """Create a WhatsApp Cloud API channel."""
    config = {
        "phone_number_id": phone_number_id,
        "access_token": access_token,
        "app_secret": app_secret,
        "verify_token": verify_token,
        "business_account_id": business_account_id,
        "graph_version": graph_version,
    }
    async with db_client.async_session() as s:
        row = ImChannelModel(
            organization_id=organization_id,
            type="whatsapp",
            name=name,
            config_encrypted=encrypt_config(config),
            enabled=enabled,
            api_key_id=None,
            created_by=user_id,
        )
        s.add(row)
        await s.commit()
        await s.refresh(row)
    # WhatsApp doesn't use the bot-side reload pub/sub (no bot process to
    # notify), but firing it is harmless and keeps future multi-channel
    # admin consoles consistent.
    await publish_reload()
    return _row_to_record(row)


async def update_whatsapp_channel(
    *,
    organization_id: int,
    channel_id: int,
    enabled: Optional[bool] = None,
    name: Optional[str] = None,
    phone_number_id: Optional[str] = None,
    access_token: Optional[str] = None,
    app_secret: Optional[str] = None,
    verify_token: Optional[str] = None,
    business_account_id: Optional[str] = None,
    graph_version: Optional[str] = None,
) -> Optional[ImChannelRecord]:
    async with db_client.async_session() as s:
        result = await s.execute(
            select(ImChannelModel).where(
                ImChannelModel.id == channel_id,
                ImChannelModel.organization_id == organization_id,
                ImChannelModel.type == "whatsapp",
            )
        )
        row = result.scalars().first()
        if row is None:
            return None
        config = decrypt_config(row.config_encrypted)
        if phone_number_id is not None:
            config["phone_number_id"] = phone_number_id
        if access_token is not None:
            config["access_token"] = access_token
        if app_secret is not None:
            config["app_secret"] = app_secret
        if verify_token is not None:
            config["verify_token"] = verify_token
        if business_account_id is not None:
            config["business_account_id"] = business_account_id
        if graph_version is not None:
            config["graph_version"] = graph_version
        if name is not None:
            row.name = name
        if enabled is not None:
            row.enabled = enabled
        row.config_encrypted = encrypt_config(config)
        await s.commit()
        await s.refresh(row)
    await publish_reload()
    return _row_to_record(row)


async def get_whatsapp_channel_by_phone_number_id(
    phone_number_id: str,
) -> Optional[ImChannelRecord]:
    """Look up the channel row a Meta webhook is addressed to.

    The webhook arrives at our endpoint with a body whose
    ``entry[].changes[].value.metadata.phone_number_id`` identifies which
    of our channels Meta is delivering to. We pick by phone_number_id
    inside the encrypted config; unfortunately the encrypted column can't
    be SQL-indexed, so this scans all enabled WhatsApp rows. Acceptable
    while the per-deployment WhatsApp channel count is small — once it
    isn't, denormalise ``phone_number_id`` to a plaintext column.
    """
    async with db_client.async_session() as s:
        result = await s.execute(
            select(ImChannelModel).where(
                ImChannelModel.type == "whatsapp",
                ImChannelModel.enabled.is_(True),
            )
        )
        rows = result.scalars().all()
    for row in rows:
        cfg = decrypt_config(row.config_encrypted)
        if str(cfg.get("phone_number_id") or "") == phone_number_id:
            return _row_to_record(row)
    return None


# --- secret bundle (internal-only) ----------------------------------------
async def all_enabled_telegram_bundles() -> list[dict[str, Any]]:
    """All enabled Telegram channels with decrypted bot_token + api_key.

    Called by the bot at boot and on every reload event. Returns the
    bundles unmasked — caller MUST gate this behind the internal auth
    middleware.
    """
    async with db_client.async_session() as s:
        result = await s.execute(
            select(ImChannelModel).where(
                ImChannelModel.type == "telegram",
                ImChannelModel.enabled.is_(True),
            )
        )
        rows = result.scalars().all()
    out: list[dict[str, Any]] = []
    for row in rows:
        cfg = decrypt_config(row.config_encrypted)
        out.append(
            {
                "id": row.id,
                "organization_id": row.organization_id,
                "name": row.name,
                "bot_token": cfg.get("bot_token", ""),
                "api_key": cfg.get("api_key", ""),
                "allowed_user_ids": cfg.get("allowed_user_ids", []),
            }
        )
    return out
