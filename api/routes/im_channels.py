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
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from loguru import logger

from api.schemas.im_channels import (
    SecretBundleEntry,
    TelegramChannelCreateRequest,
    TelegramChannelCreateResponse,
    TelegramChannelResponse,
    TelegramChannelUpdateRequest,
    TelegramTestResponse,
    WhatsAppChannelCreateRequest,
    WhatsAppChannelResponse,
    WhatsAppChannelUpdateRequest,
    WhatsAppTestResponse,
)
from api.services.auth.depends import get_user
from api.services.im import channel_service
from api.services.im.whatsapp import dispatcher as wa_dispatcher
from api.services.im.whatsapp.signature import verify_signature as wa_verify_signature

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
        logger.error("[im/secret-bundle] IM_INTERNAL_SECRET not configured — refusing")
        raise HTTPException(status_code=503, detail="im_internal_secret_unset")
    if x_im_internal_secret != expected:
        raise HTTPException(status_code=401, detail="invalid_internal_secret")
    bundles = await channel_service.all_enabled_telegram_bundles()
    return [SecretBundleEntry(**b) for b in bundles]


# --- whatsapp -------------------------------------------------------------
def _to_whatsapp_response(record) -> WhatsAppChannelResponse:
    pub = record.to_public_dict()
    return WhatsAppChannelResponse(
        id=pub["id"],
        name=pub["name"],
        enabled=pub["enabled"],
        config=pub["config"],
    )


@router.post(
    "/channels/whatsapp",
    response_model=WhatsAppChannelResponse,
    summary="Register a WhatsApp Cloud API channel. Credentials encrypted at rest.",
)
async def create_whatsapp(
    req: WhatsAppChannelCreateRequest,
    user=Depends(get_user),
) -> WhatsAppChannelResponse:
    record = await channel_service.create_whatsapp_channel(
        organization_id=user.selected_organization_id,
        user_id=user.id,
        name=req.name,
        phone_number_id=req.phone_number_id,
        access_token=req.access_token,
        app_secret=req.app_secret,
        verify_token=req.verify_token,
        business_account_id=req.business_account_id,
        graph_version=req.graph_version,
        enabled=req.enabled,
    )
    return _to_whatsapp_response(record)


@router.patch(
    "/channels/whatsapp/{channel_id}",
    response_model=WhatsAppChannelResponse,
    summary="Update a WhatsApp channel. Omitted fields are left untouched.",
)
async def update_whatsapp(
    channel_id: int,
    req: WhatsAppChannelUpdateRequest,
    user=Depends(get_user),
) -> WhatsAppChannelResponse:
    record = await channel_service.update_whatsapp_channel(
        organization_id=user.selected_organization_id,
        channel_id=channel_id,
        enabled=req.enabled,
        name=req.name,
        phone_number_id=req.phone_number_id,
        access_token=req.access_token,
        app_secret=req.app_secret,
        verify_token=req.verify_token,
        business_account_id=req.business_account_id,
        graph_version=req.graph_version,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="whatsapp_channel_not_found")
    return _to_whatsapp_response(record)


@router.delete(
    "/channels/whatsapp/{channel_id}",
    status_code=204,
    summary="Delete a WhatsApp channel.",
)
async def delete_whatsapp(
    channel_id: int,
    user=Depends(get_user),
) -> None:
    ok = await channel_service.delete_channel(
        organization_id=user.selected_organization_id,
        channel_id=channel_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="whatsapp_channel_not_found")


@router.post(
    "/channels/whatsapp/{channel_id}/test",
    response_model=WhatsAppTestResponse,
    summary="Probe the channel's Meta credentials by querying the phone number.",
)
async def test_whatsapp(
    channel_id: int,
    user=Depends(get_user),
) -> WhatsAppTestResponse:
    record = await channel_service.get_channel(
        organization_id=user.selected_organization_id,
        channel_id=channel_id,
    )
    if record is None or record.type != "whatsapp":
        raise HTTPException(status_code=404, detail="whatsapp_channel_not_found")
    cfg = record.config
    version = cfg.get("graph_version") or "v20.0"
    url = f"https://graph.facebook.com/{version}/{cfg['phone_number_id']}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            resp = await c.get(
                url,
                headers={"Authorization": f"Bearer {cfg['access_token']}"},
                params={"fields": "display_phone_number,verified_name"},
            )
    except Exception as exc:  # noqa: BLE001
        return WhatsAppTestResponse(ok=False, error=f"{type(exc).__name__}: {exc}")
    if resp.status_code != 200:
        meta_error: Optional[dict[str, Any]] = None
        try:
            meta_error = resp.json().get("error")
        except Exception:
            meta_error = None
        msg = (
            (meta_error or {}).get("message")
            if meta_error
            else f"HTTP {resp.status_code}"
        )
        return WhatsAppTestResponse(ok=False, error=msg or f"HTTP {resp.status_code}")
    body = resp.json()
    return WhatsAppTestResponse(
        ok=True,
        phone_number=body.get("display_phone_number"),
        verified_name=body.get("verified_name"),
    )


# --- whatsapp webhook (PUBLIC — Meta-facing) -----------------------------
@router.get(
    "/channels/whatsapp/{channel_id}/webhook",
    response_class=PlainTextResponse,
    summary="Meta webhook verification handshake. Public.",
    include_in_schema=False,
)
async def whatsapp_webhook_verify(
    channel_id: int,
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
) -> PlainTextResponse:
    """Implements the GET-side of Meta's webhook subscription handshake.

    Meta calls this once when the operator hits "Verify and save" in the
    Developer Console. We look up the channel row, compare the
    ``hub.verify_token`` against the channel's stored token, and echo
    ``hub.challenge`` back as plain text on success. Anything else → 403.
    """
    if hub_mode != "subscribe" or not hub_challenge:
        raise HTTPException(status_code=403, detail="invalid_hub_params")
    # Unscoped lookup — this endpoint is public and gated by the verify
    # token itself, which only the channel owner has.
    record = await channel_service.get_channel_by_id_unscoped(channel_id)
    if record is None or record.type != "whatsapp":
        raise HTTPException(status_code=404, detail="whatsapp_channel_not_found")
    expected = record.config.get("verify_token")
    if not expected or hub_verify_token != expected:
        logger.warning(
            "[whatsapp/webhook/verify] mismatch on channel_id={cid}",
            cid=channel_id,
        )
        raise HTTPException(status_code=403, detail="invalid_verify_token")
    return PlainTextResponse(hub_challenge, status_code=200)


@router.post(
    "/channels/whatsapp/{channel_id}/webhook",
    summary="Meta inbound webhook receiver. Public, signature-validated.",
    include_in_schema=False,
)
async def whatsapp_webhook_receive(
    channel_id: int,
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
) -> dict[str, Any]:
    """Receive inbound WhatsApp events from Meta.

    Body is the standard ``whatsapp_business_account`` envelope. We
    validate the HMAC-SHA256 signature against the channel's app_secret
    over the *raw* body bytes (any re-encode would break the digest),
    then parse and hand off to the dispatcher. Returns 200 quickly to
    satisfy Meta's retry policy — the heavy lifting in the dispatcher
    runs synchronously today; moving to ARQ is a documented follow-up.
    """
    raw = await request.body()

    record = await channel_service.get_channel_by_id_unscoped(channel_id)
    if record is None or record.type != "whatsapp":
        raise HTTPException(status_code=404, detail="whatsapp_channel_not_found")
    if not record.enabled:
        # Don't disclose existence; Meta will keep retrying though, so a
        # 200 + drop is gentler than an error here.
        logger.info(
            "[whatsapp/webhook] channel_id={cid} disabled; acking + dropping",
            cid=channel_id,
        )
        return {"status": "ignored"}

    app_secret = record.config.get("app_secret") or ""
    if not wa_verify_signature(
        raw_body=raw,
        signature_header=x_hub_signature_256,
        app_secret=app_secret,
    ):
        logger.warning(
            "[whatsapp/webhook] bad signature on channel_id={cid}",
            cid=channel_id,
        )
        raise HTTPException(status_code=403, detail="invalid_signature")

    # Parse and dispatch. Any exception is logged inside the dispatcher;
    # the 200 ack is unconditional below.
    try:
        from api.services.im.whatsapp.inbound_parser import parse_webhook

        payload = await request.json()
        parsed = parse_webhook(payload)
        await wa_dispatcher.dispatch(parsed)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "[whatsapp/webhook] dispatch failure on channel_id={cid}: {exc!r}",
            cid=channel_id,
            exc=exc,
        )
    return {"status": "ok"}
