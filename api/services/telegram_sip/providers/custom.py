"""Custom REST/SIP Telegram gateway provider.

Expects a gateway that exposes a minimal HTTP API:
  POST {base}/test          — credential / connectivity check
  POST {base}/calls         — initiate outbound Telegram call
  GET  {base}/calls/{id}    — call status
  POST {base}/incoming      — (optional) inbound SIP webhook handled upstream

SIP.TG and tg2sip can be configured by pointing ``gateway_api_base_url`` at their
documented REST endpoints when compatible; otherwise use provider-specific adapters.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx

from api.services.telegram_sip.base import (
    GatewayCallResult,
    GatewayConnectionTestResult,
    GatewayIncomingCallResult,
    GatewayValidationResult,
    TelegramSipGatewayProvider,
)
from api.services.telegram_sip.config import TelegramSipGatewayConfig
from api.services.telegram_sip.logging_utils import log_gateway_request, log_gateway_response


class GatewayProviderError(Exception):
    """Raised when the external gateway returns an error."""

    def __init__(self, code: str, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _api_base(config: TelegramSipGatewayConfig) -> str:
    base = (config.credentials.gateway_api_base_url or "").rstrip("/")
    if not base:
        raise GatewayProviderError(
            "invalid_config",
            "gateway_api_base_url is required for custom gateways",
        )
    return base


def _auth_headers(config: TelegramSipGatewayConfig) -> Dict[str, str]:
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    api_key = config.credentials.gateway_api_key
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _sip_payload(config: TelegramSipGatewayConfig) -> Dict[str, Any]:
    creds = config.credentials
    return {
        "sip_host": creds.sip_host,
        "sip_port": creds.sip_port,
        "sip_username": creds.sip_username,
        "sip_password": creds.sip_password,
        "sip_caller_id": creds.sip_caller_id,
        "telegram_destination_id": creds.telegram_destination_id,
        "webhook_callback_url": creds.webhook_callback_url,
        "gateway_provider_type": config.gateway_provider_type,
    }


def _map_http_error(exc: httpx.HTTPStatusError) -> GatewayProviderError:
    status = exc.response.status_code
    if status in (401, 403):
        return GatewayProviderError("invalid_credentials", "Invalid SIP or API credentials", status_code=status)
    if status == 404:
        return GatewayProviderError("telegram_unreachable", "Telegram destination not reachable", status_code=status)
    if status == 415 or status == 488:
        return GatewayProviderError("unsupported_codec", "Unsupported codec or media type", status_code=status)
    if status >= 500:
        return GatewayProviderError("gateway_unavailable", "Gateway unavailable", status_code=status)
    return GatewayProviderError("call_setup_failed", f"Gateway error (HTTP {status})", status_code=status)


class CustomSipTelegramGatewayProvider(TelegramSipGatewayProvider):
    PROVIDER_TYPE = "custom"

    def validate_config(self, config: TelegramSipGatewayConfig) -> GatewayValidationResult:
        creds = config.credentials
        if config.gateway_provider_type == "custom" and not creds.gateway_api_base_url:
            return GatewayValidationResult(
                ok=False,
                message="gateway_api_base_url is required for custom provider",
            )
        if config.gateway_provider_type in ("sip_tg", "tg2sip") and not creds.gateway_api_base_url:
            return GatewayValidationResult(
                ok=False,
                message=f"gateway_api_base_url is required for {config.gateway_provider_type}",
            )
        return GatewayValidationResult(ok=True, message="Configuration valid")

    async def test_connection(
        self, config: TelegramSipGatewayConfig
    ) -> GatewayConnectionTestResult:
        validation = self.validate_config(config)
        if not validation.ok:
            return GatewayConnectionTestResult(ok=False, message=validation.message or "Invalid config")

        base = _api_base(config)
        url = urljoin(base + "/", "test")
        log_gateway_request(provider_type=config.gateway_provider_type, operation="test_connection")
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    json=_sip_payload(config),
                    headers=_auth_headers(config),
                )
                response.raise_for_status()
        except httpx.ConnectError:
            log_gateway_response(
                provider_type=config.gateway_provider_type,
                operation="test_connection",
                ok=False,
            )
            return GatewayConnectionTestResult(
                ok=False, message="Gateway unavailable (connection failed)"
            )
        except httpx.HTTPStatusError as exc:
            err = _map_http_error(exc)
            log_gateway_response(
                provider_type=config.gateway_provider_type,
                operation="test_connection",
                ok=False,
                extra={"error_code": err.code},
            )
            return GatewayConnectionTestResult(ok=False, message=err.message)
        except GatewayProviderError as exc:
            return GatewayConnectionTestResult(ok=False, message=exc.message)

        latency_ms = (time.perf_counter() - started) * 1000
        log_gateway_response(
            provider_type=config.gateway_provider_type,
            operation="test_connection",
            ok=True,
            extra={"latency_ms": round(latency_ms, 2)},
        )
        return GatewayConnectionTestResult(
            ok=True,
            message="Gateway connection successful",
            latency_ms=round(latency_ms, 2),
        )

    async def initiate_call(
        self,
        config: TelegramSipGatewayConfig,
        destination: str,
        *,
        webhook_url: Optional[str] = None,
    ) -> GatewayCallResult:
        base = _api_base(config)
        url = urljoin(base + "/", "calls")
        body = {
            **_sip_payload(config),
            "destination": destination,
            "callback_url": webhook_url or config.credentials.webhook_callback_url,
        }
        log_gateway_request(
            provider_type=config.gateway_provider_type,
            operation="initiate_call",
            extra={"destination": destination},
        )
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url, json=body, headers=_auth_headers(config)
                )
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError as exc:
            raise GatewayProviderError("gateway_unavailable", "Gateway unavailable") from exc
        except httpx.HTTPStatusError as exc:
            raise _map_http_error(exc) from exc

        call_id = str(data.get("call_id") or data.get("id") or "")
        status = str(data.get("status") or "ringing")
        log_gateway_response(
            provider_type=config.gateway_provider_type,
            operation="initiate_call",
            ok=True,
            extra={"call_id": call_id, "status": status},
        )
        return GatewayCallResult(
            call_id=call_id,
            status=status,
            provider_metadata=data,
        )

    async def handle_incoming_call(
        self, config: TelegramSipGatewayConfig, payload: Dict[str, Any]
    ) -> GatewayIncomingCallResult:
        """Route inbound SIP events to the configured Telegram destination."""
        call_id = str(payload.get("call_id") or payload.get("id") or "")
        from_addr = payload.get("from") or payload.get("caller") or "unknown"
        log_gateway_request(
            provider_type=config.gateway_provider_type,
            operation="handle_incoming_call",
            extra={"call_id": call_id, "from": from_addr},
        )

        base = _api_base(config)
        url = urljoin(base + "/", "incoming")
        body = {
            **_sip_payload(config),
            "incoming": payload,
            "route_to": config.credentials.telegram_destination_id,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url, json=body, headers=_auth_headers(config)
                )
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError:
            return GatewayIncomingCallResult(
                routed=False,
                call_id=call_id,
                status="failed",
                message="Gateway unavailable",
            )
        except httpx.HTTPStatusError:
            return GatewayIncomingCallResult(
                routed=False,
                call_id=call_id,
                status="failed",
                message="Failed to route incoming call",
            )

        routed = bool(data.get("routed", True))
        status = str(data.get("status") or "ringing")
        log_gateway_response(
            provider_type=config.gateway_provider_type,
            operation="handle_incoming_call",
            ok=routed,
            extra={"call_id": call_id, "status": status},
        )
        return GatewayIncomingCallResult(
            routed=routed,
            call_id=str(data.get("call_id") or call_id),
            status=status,
            message=data.get("message"),
            provider_metadata=data,
        )

    async def get_call_status(
        self, config: TelegramSipGatewayConfig, call_id: str
    ) -> Dict[str, Any]:
        base = _api_base(config)
        url = urljoin(base + "/", f"calls/{call_id}")
        log_gateway_request(
            provider_type=config.gateway_provider_type,
            operation="get_call_status",
            extra={"call_id": call_id},
        )
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=_auth_headers(config))
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError as exc:
            raise GatewayProviderError("gateway_unavailable", "Gateway unavailable") from exc
        except httpx.HTTPStatusError as exc:
            raise _map_http_error(exc) from exc

        log_gateway_response(
            provider_type=config.gateway_provider_type,
            operation="get_call_status",
            ok=True,
            extra={"status": data.get("status")},
        )
        return data
