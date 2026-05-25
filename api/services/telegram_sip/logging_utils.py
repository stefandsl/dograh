"""Structured logging helpers for Telegram SIP gateway operations."""

from typing import Any, Dict, Optional

from loguru import logger

from api.services.telegram_sip.config import SENSITIVE_CREDENTIAL_FIELDS


def _redact(data: Dict[str, Any]) -> Dict[str, Any]:
    redacted = dict(data)
    for key in list(redacted):
        if key in SENSITIVE_CREDENTIAL_FIELDS or "password" in key.lower():
            redacted[key] = "[REDACTED]"
    return redacted


def log_gateway_request(
    *,
    provider_type: str,
    operation: str,
    config_id: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    logger.info(
        "telegram_sip_gateway request",
        provider_type=provider_type,
        operation=operation,
        config_id=config_id,
        extra=_redact(extra or {}),
    )


def log_gateway_response(
    *,
    provider_type: str,
    operation: str,
    ok: bool,
    config_id: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    level = logger.info if ok else logger.warning
    level(
        "telegram_sip_gateway response",
        provider_type=provider_type,
        operation=operation,
        ok=ok,
        config_id=config_id,
        extra=_redact(extra or {}),
    )


def log_call_lifecycle(
    *,
    config_id: int,
    call_log_id: int,
    status: str,
    gateway_call_id: Optional[str] = None,
    direction: Optional[str] = None,
    error_code: Optional[str] = None,
) -> None:
    logger.info(
        "telegram_sip_call lifecycle",
        config_id=config_id,
        call_log_id=call_log_id,
        status=status,
        gateway_call_id=gateway_call_id,
        direction=direction,
        error_code=error_code,
    )
