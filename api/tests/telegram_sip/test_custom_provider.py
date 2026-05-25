from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from api.services.telegram_sip.config import (
    TelegramSipGatewayConfig,
    TelegramSipGatewayCredentials,
)
from api.services.telegram_sip.providers.custom import (
    CustomSipTelegramGatewayProvider,
    GatewayProviderError,
)


def _config(provider_type: str = "custom") -> TelegramSipGatewayConfig:
    return TelegramSipGatewayConfig(
        gateway_provider_type=provider_type,
        credentials=TelegramSipGatewayCredentials(
            sip_host="sip.example.com",
            sip_port=5060,
            sip_username="user",
            sip_password="secret",
            sip_caller_id="+10000000001",
            telegram_destination_id="@mybot",
            gateway_api_base_url="https://gateway.example.com/api",
            gateway_api_key="api-key",
        ),
    )


class TestCustomSipTelegramGatewayProvider:
    def test_validate_config_requires_api_base_url(self):
        provider = CustomSipTelegramGatewayProvider()
        config = TelegramSipGatewayConfig(
            gateway_provider_type="custom",
            credentials=TelegramSipGatewayCredentials(
                sip_host="sip.example.com",
                sip_port=5060,
                sip_username="user",
                sip_password="secret",
                sip_caller_id="+1",
                telegram_destination_id="@bot",
            ),
        )
        result = provider.validate_config(config)
        assert result.ok is False
        assert "gateway_api_base_url" in (result.message or "")

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        provider = CustomSipTelegramGatewayProvider()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "api.services.telegram_sip.providers.custom.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await provider.test_connection(_config())
        assert result.ok is True

    @pytest.mark.asyncio
    async def test_initiate_call_maps_gateway_error(self):
        provider = CustomSipTelegramGatewayProvider()
        request = httpx.Request("POST", "https://gateway.example.com/api/calls")
        response = httpx.Response(401, request=request)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError("auth", request=request, response=response)
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "api.services.telegram_sip.providers.custom.httpx.AsyncClient",
            return_value=mock_client,
        ):
            with pytest.raises(GatewayProviderError) as exc:
                await provider.initiate_call(_config(), "@dest")
        assert exc.value.code == "invalid_credentials"

    @pytest.mark.asyncio
    async def test_initiate_call_success(self):
        provider = CustomSipTelegramGatewayProvider()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={"call_id": "gw-123", "status": "ringing"}
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "api.services.telegram_sip.providers.custom.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await provider.initiate_call(_config(), "@dest")
        assert result.call_id == "gw-123"
        assert result.status == "ringing"
