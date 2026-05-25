"""Routes for SIP-to-Telegram gateway configuration and calls."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger

from api.db import db_client
from api.db.models import UserModel
from api.schemas.telegram_sip_gateway import (
    TelegramSipCallLogListResponse,
    TelegramSipCallLogResponse,
    TelegramSipGatewayConfigCreateRequest,
    TelegramSipGatewayConfigDetail,
    TelegramSipGatewayConfigListItem,
    TelegramSipGatewayConfigListResponse,
    TelegramSipGatewayConfigUpdateRequest,
    TelegramSipGatewayTestResponse,
    TelegramSipInitiateCallRequest,
    TelegramSipProviderMetadataField,
    TelegramSipProvidersMetadataResponse,
)
from api.services.auth.depends import get_user
from api.services.configuration.masking import is_mask_of, mask_key
from api.services.telegram_sip.config import SENSITIVE_CREDENTIAL_FIELDS
from api.services.telegram_sip.providers.custom import GatewayProviderError
from api.services.telegram_sip.service import TelegramSipService

router = APIRouter(
    prefix="/organizations/telegram-sip-gateway",
    tags=["telegram-sip-gateway"],
)

_service = TelegramSipService()

_UI_FIELDS = [
    TelegramSipProviderMetadataField(
        name="gateway_provider_type",
        label="Gateway Provider",
        type="select",
        description="sip_tg, tg2sip, or custom REST gateway",
    ),
    TelegramSipProviderMetadataField(
        name="sip_host", label="SIP Server / Host", type="text", required=True
    ),
    TelegramSipProviderMetadataField(
        name="sip_port", label="SIP Port", type="number", required=True
    ),
    TelegramSipProviderMetadataField(
        name="sip_username", label="SIP Username", type="text", required=True
    ),
    TelegramSipProviderMetadataField(
        name="sip_password",
        label="SIP Password",
        type="password",
        required=True,
        sensitive=True,
    ),
    TelegramSipProviderMetadataField(
        name="sip_caller_id", label="SIP Caller ID / Number", type="text", required=True
    ),
    TelegramSipProviderMetadataField(
        name="telegram_destination_id",
        label="Telegram Account / Routing ID",
        type="text",
        required=True,
    ),
    TelegramSipProviderMetadataField(
        name="gateway_api_base_url",
        label="Gateway API Base URL",
        type="text",
        description="REST base URL for the external gateway",
    ),
    TelegramSipProviderMetadataField(
        name="gateway_api_key",
        label="Gateway API Key",
        type="password",
        sensitive=True,
    ),
    TelegramSipProviderMetadataField(
        name="webhook_callback_url",
        label="Webhook Callback URL",
        type="text",
        required=False,
    ),
]


def _require_org(user: UserModel) -> int:
    if not user.selected_organization_id:
        raise HTTPException(status_code=400, detail="No organization selected")
    return user.selected_organization_id


def _mask_credentials(credentials: dict) -> dict:
    out = dict(credentials or {})
    for field_name in SENSITIVE_CREDENTIAL_FIELDS:
        value = out.get(field_name)
        if value:
            out[field_name] = mask_key(value)
    if out.get("sip_password"):
        out["sip_password"] = mask_key(out["sip_password"])
    return out


def _preserve_masked(existing: dict, incoming: dict) -> dict:
    merged = dict(incoming)
    for field_name in SENSITIVE_CREDENTIAL_FIELDS | {"sip_password"}:
        value = merged.get(field_name)
        if value and is_mask_of(value, existing.get(field_name, "")):
            merged[field_name] = existing[field_name]
    return merged


def _detail(row) -> TelegramSipGatewayConfigDetail:
    masked = _mask_credentials(row.credentials or {})
    return TelegramSipGatewayConfigDetail(
        id=row.id,
        name=row.name,
        gateway_provider_type=row.gateway_provider_type,
        is_enabled=row.is_enabled,
        credentials=masked,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _call_log_response(row) -> TelegramSipCallLogResponse:
    return TelegramSipCallLogResponse(
        id=row.id,
        configuration_id=row.configuration_id,
        gateway_call_id=row.gateway_call_id,
        direction=row.direction,
        destination=row.destination,
        status=row.status,
        error_code=row.error_code,
        error_message=row.error_message,
        events=row.events or [],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _get_config_or_404(config_id: int, organization_id: int):
    row = await db_client.get_gateway_configuration_for_org(config_id, organization_id)
    if not row:
        raise HTTPException(status_code=404, detail="telegram_sip_gateway_not_found")
    return row


@router.get("/metadata", response_model=TelegramSipProvidersMetadataResponse)
async def get_providers_metadata(user: UserModel = Depends(get_user)):
    _require_org(user)
    from api.services.telegram_sip import registry as gateway_registry

    import api.services.telegram_sip.providers  # noqa: F401

    return TelegramSipProvidersMetadataResponse(
        provider_types=gateway_registry.registered_types(),
        fields=_UI_FIELDS,
    )


@router.get("/configs", response_model=TelegramSipGatewayConfigListResponse)
async def list_configurations(user: UserModel = Depends(get_user)):
    org_id = _require_org(user)
    rows = await db_client.list_gateway_configurations(org_id)
    return TelegramSipGatewayConfigListResponse(
        configurations=[
            TelegramSipGatewayConfigListItem(
                id=r.id,
                name=r.name,
                gateway_provider_type=r.gateway_provider_type,
                is_enabled=r.is_enabled,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]
    )


@router.post("/configs", response_model=TelegramSipGatewayConfigDetail)
async def create_configuration(
    request: TelegramSipGatewayConfigCreateRequest,
    user: UserModel = Depends(get_user),
):
    org_id = _require_org(user)
    credentials = request.credentials.model_dump()
    try:
        await _service.validate_before_save(
            request.gateway_provider_type, credentials
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    row = await db_client.create_gateway_configuration(
        organization_id=org_id,
        name=request.name,
        gateway_provider_type=request.gateway_provider_type,
        credentials=credentials,
        is_enabled=request.is_enabled,
    )
    logger.info(
        "Created Telegram SIP gateway config",
        config_id=row.id,
        organization_id=org_id,
        provider_type=request.gateway_provider_type,
    )
    return _detail(row)


@router.get("/configs/{config_id}", response_model=TelegramSipGatewayConfigDetail)
async def get_configuration(config_id: int, user: UserModel = Depends(get_user)):
    org_id = _require_org(user)
    row = await _get_config_or_404(config_id, org_id)
    return _detail(row)


@router.put("/configs/{config_id}", response_model=TelegramSipGatewayConfigDetail)
async def update_configuration(
    config_id: int,
    request: TelegramSipGatewayConfigUpdateRequest,
    user: UserModel = Depends(get_user),
):
    org_id = _require_org(user)
    existing = await _get_config_or_404(config_id, org_id)

    credentials = existing.credentials
    provider_type = existing.gateway_provider_type
    if request.credentials is not None:
        incoming = request.credentials.model_dump()
        credentials = _preserve_masked(existing.credentials or {}, incoming)
    if request.gateway_provider_type is not None:
        provider_type = request.gateway_provider_type

    try:
        await _service.validate_before_save(provider_type, credentials or {})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    row = await db_client.update_gateway_configuration(
        config_id,
        org_id,
        name=request.name,
        credentials=credentials if request.credentials is not None else None,
        is_enabled=request.is_enabled,
        gateway_provider_type=request.gateway_provider_type,
    )
    return _detail(row)


@router.delete("/configs/{config_id}")
async def delete_configuration(config_id: int, user: UserModel = Depends(get_user)):
    org_id = _require_org(user)
    deleted = await db_client.delete_gateway_configuration(config_id, org_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="telegram_sip_gateway_not_found")
    return {"ok": True}


@router.post("/configs/{config_id}/test", response_model=TelegramSipGatewayTestResponse)
async def test_configuration(config_id: int, user: UserModel = Depends(get_user)):
    org_id = _require_org(user)
    row = await _get_config_or_404(config_id, org_id)
    result = await _service.test_connection(row)
    return TelegramSipGatewayTestResponse(**result)


@router.post("/configs/{config_id}/calls", response_model=TelegramSipCallLogResponse)
async def initiate_call(
    config_id: int,
    request: TelegramSipInitiateCallRequest,
    user: UserModel = Depends(get_user),
):
    org_id = _require_org(user)
    row = await _get_config_or_404(config_id, org_id)
    try:
        call_log = await _service.initiate_call(
            row,
            destination=request.destination,
            webhook_url=request.webhook_url,
        )
    except GatewayProviderError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _call_log_response(call_log)


@router.get("/configs/{config_id}/calls", response_model=TelegramSipCallLogListResponse)
async def list_calls(config_id: int, user: UserModel = Depends(get_user)):
    org_id = _require_org(user)
    await _get_config_or_404(config_id, org_id)
    rows = await db_client.list_call_logs(org_id, configuration_id=config_id)
    return TelegramSipCallLogListResponse(
        call_logs=[_call_log_response(r) for r in rows]
    )


@router.get(
    "/configs/{config_id}/calls/{call_log_id}",
    response_model=TelegramSipCallLogResponse,
)
async def get_call(
    config_id: int,
    call_log_id: int,
    user: UserModel = Depends(get_user),
):
    org_id = _require_org(user)
    await _get_config_or_404(config_id, org_id)
    call_log = await db_client.get_call_log_for_org(call_log_id, org_id)
    if not call_log or call_log.configuration_id != config_id:
        raise HTTPException(status_code=404, detail="call_log_not_found")
    return _call_log_response(call_log)


@router.post(
    "/configs/{config_id}/calls/{call_log_id}/refresh",
    response_model=TelegramSipCallLogResponse,
)
async def refresh_call_status(
    config_id: int,
    call_log_id: int,
    user: UserModel = Depends(get_user),
):
    org_id = _require_org(user)
    row = await _get_config_or_404(config_id, org_id)
    call_log = await db_client.get_call_log_for_org(call_log_id, org_id)
    if not call_log or call_log.configuration_id != config_id:
        raise HTTPException(status_code=404, detail="call_log_not_found")
    try:
        updated = await _service.refresh_call_status(row, call_log)
    except GatewayProviderError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return _call_log_response(updated)


# Public webhook router — no user session; gateways POST call events here.
public_router = APIRouter(
    prefix="/telegram-sip-gateway/webhooks",
    tags=["telegram-sip-gateway-webhooks"],
)


async def _get_enabled_config(config_id: int):
    row = await db_client.get_gateway_configuration(config_id)
    if not row or not row.is_enabled:
        raise HTTPException(status_code=404, detail="telegram_sip_gateway_not_found")
    return row


@public_router.post("/{config_id}/incoming", response_model=TelegramSipCallLogResponse)
async def public_incoming_call_webhook(config_id: int, request: Request):
    """Handle inbound SIP events posted by the external gateway (no user auth)."""
    row = await _get_enabled_config(config_id)
    payload = await request.json()
    call_log = await _service.handle_incoming_webhook(row, payload)
    return _call_log_response(call_log)


@public_router.post("/{config_id}/status", response_model=TelegramSipCallLogResponse)
async def public_call_status_webhook(config_id: int, request: Request):
    """Apply call status updates (ringing, connected, failed, completed) from gateway."""
    row = await _get_enabled_config(config_id)
    payload = await request.json()
    gateway_call_id = str(payload.get("call_id") or payload.get("id") or "")
    if not gateway_call_id:
        raise HTTPException(status_code=422, detail="call_id_required")

    updated = await _service.apply_status_webhook(
        row,
        gateway_call_id=gateway_call_id,
        status=str(payload.get("status") or "unknown"),
        error_code=payload.get("error_code"),
        error_message=payload.get("error_message"),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="call_log_not_found")
    return _call_log_response(updated)
