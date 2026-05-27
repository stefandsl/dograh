"""IM channels CRUD router.

Phase 4a — Telegram only. WhatsApp and Discord tabs in the UI are
greyed-out placeholders.

Auth: every endpoint takes ``Depends(get_user)`` and scopes by
``user.selected_organization_id``. The internal ``/secret-bundle``
endpoint is gated by an in-process service token (env
``IM_INTERNAL_SECRET``) so only the bot container can pull plaintext
credentials.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from loguru import logger

from api.schemas.im_channels import (
    SecretBundleEntry,
    TelegramChannelCreateRequest,
    TelegramChannelCreateResponse,
    TelegramChannelResponse,
    TelegramChannelUpdateRequest,
    TelegramTestResponse,
)
from api.services.auth.depends import get_user
from api.services.im import channel_service


router = APIRouter(prefix="/im", tags=["im-channels"])


def _to_response(record) -> TelegramChannelResponse:
    pub = record.to_public_dict()
    return TelegramChannelResponse(
        id=pub["id"],
        name=pub["name"],
        enabled=pub["enabled"],
        api_key_id=pub["api_key_id"],
        config=pub["config"],
    )


# --- list -----------------------------------------------------------------
@router.get(
    "/channels",
    response_model=list[TelegramChannelResponse],
    summary="List IM channels (Telegram only for now).",
)
async def list_channels(
    type: Optional[str] = "telegram",
    enabled: Optional[bool] = None,
    user=Depends(get_user),
) -> list[TelegramChannelResponse]:
    records = await channel_service.list_channels(
        organization_id=user.selected_organization_id,
        type_filter=type,
    )
    if enabled is not None:
        records = [r for r in records if r.enabled is enabled]
    return [_to_response(r) for r in records]


# --- create ---------------------------------------------------------------
@router.post(
    "/channels/telegram",
    response_model=TelegramChannelCreateResponse,
    summary="Register a Telegram bot token. Auto-mints a service API key.",
)
async def create_telegram(
    req: TelegramChannelCreateRequest,
    user=Depends(get_user),
) -> TelegramChannelCreateResponse:
    record, raw_key = await channel_service.create_telegram_channel(
        organization_id=user.selected_organization_id,
        user_id=user.id,
        name=req.name,
        bot_token=req.bot_token,
        allowed_user_ids=req.allowed_user_ids,
        enabled=req.enabled,
    )
    pub = record.to_public_dict()
    return TelegramChannelCreateResponse(
        id=pub["id"],
        name=pub["name"],
        enabled=pub["enabled"],
        api_key_id=pub["api_key_id"],
        config=pub["config"],
        api_key=raw_key,
    )


# --- update ---------------------------------------------------------------
@router.patch(
    "/channels/telegram/{channel_id}",
    response_model=TelegramChannelResponse,
)
async def update_telegram(
    channel_id: int,
    req: TelegramChannelUpdateRequest,
    user=Depends(get_user),
) -> TelegramChannelResponse:
    record = await channel_service.update_telegram_channel(
        organization_id=user.selected_organization_id,
        channel_id=channel_id,
        enabled=req.enabled,
        allowed_user_ids=req.allowed_user_ids,
        bot_token=req.bot_token,
        name=req.name,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="im_channel_not_found")
    return _to_response(record)


# --- delete ---------------------------------------------------------------
@router.delete(
    "/channels/telegram/{channel_id}",
    status_code=204,
)
async def delete_telegram(
    channel_id: int,
    user=Depends(get_user),
) -> None:
    ok = await channel_service.delete_channel(
        organization_id=user.selected_organization_id,
        channel_id=channel_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="im_channel_not_found")


# --- test connection ------------------------------------------------------
@router.post(
    "/channels/telegram/{channel_id}/test",
    response_model=TelegramTestResponse,
    summary="Calls Telegram /getMe with the stored token.",
)
async def test_telegram(
    channel_id: int,
    user=Depends(get_user),
) -> TelegramTestResponse:
    record = await channel_service.get_channel(
        organization_id=user.selected_organization_id,
        channel_id=channel_id,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="im_channel_not_found")
    bot_token = record.config.get("bot_token", "")
    result = await channel_service.test_telegram_token(bot_token)
    return TelegramTestResponse(**result)


# --- rotate api key -------------------------------------------------------
@router.post(
    "/channels/telegram/{channel_id}/rotate-api-key",
    response_model=TelegramChannelCreateResponse,
)
async def rotate_telegram_api_key(
    channel_id: int,
    user=Depends(get_user),
) -> TelegramChannelCreateResponse:
    result = await channel_service.rotate_api_key(
        organization_id=user.selected_organization_id,
        channel_id=channel_id,
        user_id=user.id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="im_channel_not_found")
    record, raw = result
    pub = record.to_public_dict()
    return TelegramChannelCreateResponse(
        id=pub["id"],
        name=pub["name"],
        enabled=pub["enabled"],
        api_key_id=pub["api_key_id"],
        config=pub["config"],
        api_key=raw,
    )


# --- secret bundle (bot-only) --------------------------------------------
@router.get(
    "/channels/secret-bundle",
    response_model=list[SecretBundleEntry],
    summary="Internal — returns plaintext bot_token + api_key for every "
            "enabled Telegram channel. Gated by IM_INTERNAL_SECRET header.",
    include_in_schema=False,
)
async def get_secret_bundle(
    x_im_internal_secret: Optional[str] = Header(None),
) -> list[SecretBundleEntry]:
    expected = os.getenv("IM_INTERNAL_SECRET")
    if not expected:
        logger.error(
            "[im/secret-bundle] IM_INTERNAL_SECRET not configured — refusing"
        )
        raise HTTPException(status_code=503, detail="im_internal_secret_unset")
    if x_im_internal_secret != expected:
        raise HTTPException(status_code=401, detail="invalid_internal_secret")
    bundles = await channel_service.all_enabled_telegram_bundles()
    return [SecretBundleEntry(**b) for b in bundles]
