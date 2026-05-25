from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from api.services.telegram_sip.providers.custom import GatewayProviderError
from api.services.telegram_sip.service import TelegramSipService


def _row(**kwargs):
    defaults = {
        "id": 1,
        "organization_id": 10,
        "gateway_provider_type": "custom",
        "is_enabled": True,
        "credentials": {
            "sip_host": "sip.example.com",
            "sip_port": 5060,
            "sip_username": "user",
            "sip_password": "secret",
            "sip_caller_id": "+1",
            "telegram_destination_id": "@bot",
            "gateway_api_base_url": "https://gateway.example.com/api",
        },
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestTelegramSipService:
    @pytest.mark.asyncio
    async def test_validate_before_save_rejects_invalid(self):
        service = TelegramSipService()
        with pytest.raises(ValueError, match="gateway_api_base_url"):
            await service.validate_before_save(
                "custom",
                {
                    "sip_host": "h",
                    "sip_username": "u",
                    "sip_password": "p",
                    "sip_caller_id": "c",
                    "telegram_destination_id": "t",
                },
            )

    @pytest.mark.asyncio
    async def test_initiate_call_records_failure(self):
        service = TelegramSipService()
        row = _row()
        call_log = SimpleNamespace(id=99, organization_id=10, configuration_id=1)

        with (
            patch("api.services.telegram_sip.service.db_client") as mock_db,
            patch.object(
                service,
                "_provider_for",
            ) as mock_provider_for,
        ):
            mock_db.create_call_log = AsyncMock(return_value=call_log)
            mock_db.update_call_log = AsyncMock(return_value=call_log)
            provider = AsyncMock()
            provider.initiate_call = AsyncMock(
                side_effect=GatewayProviderError("gateway_unavailable", "down")
            )
            mock_provider_for.return_value = provider

            with pytest.raises(GatewayProviderError):
                await service.initiate_call(row, destination="@user")

            mock_db.update_call_log.assert_awaited()
            kwargs = mock_db.update_call_log.await_args.kwargs
            assert kwargs["status"] == "failed"
            assert kwargs["error_code"] == "gateway_unavailable"
