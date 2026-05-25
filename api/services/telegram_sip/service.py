"""Service layer for Telegram SIP gateway operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from api.db import db_client
from api.db.models import TelegramSipCallLogModel, TelegramSipGatewayConfigurationModel
from api.services.telegram_sip.config import TelegramSipGatewayConfig, TelegramSipGatewayCredentials
from api.services.telegram_sip.logging_utils import log_call_lifecycle
from api.services.telegram_sip.providers.custom import GatewayProviderError
from api.services.telegram_sip import registry as gateway_registry

# Ensure providers are registered on import.
import api.services.telegram_sip.providers  # noqa: F401


_TERMINAL_STATUSES = frozenset({"completed", "failed", "busy", "no_answer", "canceled"})


class TelegramSipService:
    def build_config(self, row: TelegramSipGatewayConfigurationModel) -> TelegramSipGatewayConfig:
        creds = TelegramSipGatewayCredentials.model_validate(row.credentials or {})
        return TelegramSipGatewayConfig(
            gateway_provider_type=row.gateway_provider_type,
            credentials=creds,
        )

    def _provider_for(self, config: TelegramSipGatewayConfig):
        return gateway_registry.get(config.gateway_provider_type)

    async def validate_before_save(
        self, gateway_provider_type: str, credentials: Dict[str, Any]
    ) -> None:
        config = TelegramSipGatewayConfig(
            gateway_provider_type=gateway_provider_type,
            credentials=TelegramSipGatewayCredentials.model_validate(credentials),
        )
        provider = self._provider_for(config)
        result = provider.validate_config(config)
        if not result.ok:
            raise ValueError(result.message or "Invalid gateway configuration")

    async def test_connection(
        self, row: TelegramSipGatewayConfigurationModel
    ) -> Dict[str, Any]:
        config = self.build_config(row)
        provider = self._provider_for(config)
        result = await provider.test_connection(config)
        return {
            "ok": result.ok,
            "message": result.message,
            "latency_ms": result.latency_ms,
            "details": result.details,
        }

    async def initiate_call(
        self,
        row: TelegramSipGatewayConfigurationModel,
        *,
        destination: str,
        webhook_url: Optional[str] = None,
    ) -> TelegramSipCallLogModel:
        if not row.is_enabled:
            raise ValueError("Gateway configuration is disabled")

        config = self.build_config(row)
        provider = self._provider_for(config)

        call_log = await db_client.create_call_log(
            organization_id=row.organization_id,
            configuration_id=row.id,
            direction="outbound",
            destination=destination,
            status="initiated",
        )
        log_call_lifecycle(
            config_id=row.id,
            call_log_id=call_log.id,
            status="initiated",
            direction="outbound",
        )

        try:
            result = await provider.initiate_call(
                config, destination, webhook_url=webhook_url
            )
        except GatewayProviderError as exc:
            await db_client.update_call_log(
                call_log.id,
                row.organization_id,
                status="failed",
                error_code=exc.code,
                error_message=exc.message,
                append_event={"event": "failed", "source": "gateway"},
            )
            log_call_lifecycle(
                config_id=row.id,
                call_log_id=call_log.id,
                status="failed",
                error_code=exc.code,
            )
            raise

        status = self._normalize_status(result.status)
        updated = await db_client.update_call_log(
            call_log.id,
            row.organization_id,
            status=status,
            gateway_call_id=result.call_id or None,
            append_event={
                "event": status,
                "source": "gateway",
                "metadata": {"provider": result.provider_metadata},
            },
        )
        log_call_lifecycle(
            config_id=row.id,
            call_log_id=call_log.id,
            status=status,
            gateway_call_id=result.call_id,
        )
        return updated or call_log

    async def handle_incoming_webhook(
        self,
        row: TelegramSipGatewayConfigurationModel,
        payload: Dict[str, Any],
    ) -> TelegramSipCallLogModel:
        config = self.build_config(row)
        provider = self._provider_for(config)

        from_addr = str(
            payload.get("from")
            or payload.get("caller")
            or payload.get("from_number")
            or "unknown"
        )
        call_log = await db_client.create_call_log(
            organization_id=row.organization_id,
            configuration_id=row.id,
            direction="inbound",
            destination=from_addr,
            status="ringing",
        )
        log_call_lifecycle(
            config_id=row.id,
            call_log_id=call_log.id,
            status="ringing",
            direction="inbound",
        )

        result = await provider.handle_incoming_call(config, payload)
        status = "connected" if result.routed else "failed"
        error_code = None if result.routed else "call_setup_failed"
        updated = await db_client.update_call_log(
            call_log.id,
            row.organization_id,
            status=status,
            gateway_call_id=result.call_id,
            error_code=error_code,
            error_message=result.message,
            append_event={
                "event": status,
                "source": "gateway",
                "metadata": result.provider_metadata,
            },
        )
        log_call_lifecycle(
            config_id=row.id,
            call_log_id=call_log.id,
            status=status,
            gateway_call_id=result.call_id,
            error_code=error_code,
        )
        return updated or call_log

    async def refresh_call_status(
        self, row: TelegramSipGatewayConfigurationModel, call_log: TelegramSipCallLogModel
    ) -> TelegramSipCallLogModel:
        if not call_log.gateway_call_id:
            return call_log

        config = self.build_config(row)
        provider = self._provider_for(config)
        try:
            data = await provider.get_call_status(config, call_log.gateway_call_id)
        except GatewayProviderError as exc:
            await db_client.update_call_log(
                call_log.id,
                row.organization_id,
                error_code=exc.code,
                error_message=exc.message,
                append_event={"event": "status_fetch_failed", "source": "gateway"},
            )
            raise

        status = self._normalize_status(str(data.get("status") or call_log.status))
        updated = await db_client.update_call_log(
            call_log.id,
            row.organization_id,
            status=status,
            append_event={"event": status, "source": "gateway", "metadata": data},
        )
        log_call_lifecycle(
            config_id=row.id,
            call_log_id=call_log.id,
            status=status,
            gateway_call_id=call_log.gateway_call_id,
        )
        return updated or call_log

    async def apply_status_webhook(
        self,
        row: TelegramSipGatewayConfigurationModel,
        *,
        gateway_call_id: str,
        status: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[TelegramSipCallLogModel]:
        call_log = await db_client.get_call_log_by_gateway_id(
            gateway_call_id, row.id
        )
        if not call_log:
            return None

        normalized = self._normalize_status(status)
        return await db_client.update_call_log(
            call_log.id,
            row.organization_id,
            status=normalized,
            error_code=error_code,
            error_message=error_message,
            append_event={"event": normalized, "source": "webhook"},
        )

    @staticmethod
    def _normalize_status(raw: str) -> str:
        value = (raw or "initiated").lower().replace("-", "_")
        mapping = {
            "in_progress": "connected",
            "answered": "connected",
            "busy": "failed",
            "no_answer": "failed",
            "cancelled": "completed",
            "canceled": "completed",
        }
        return mapping.get(value, value)
