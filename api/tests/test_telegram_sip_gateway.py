"""API and configuration tests for Telegram SIP gateway."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.telegram_sip_gateway import public_router, router
from api.services.auth.depends import get_user
from api.services.configuration.masking import mask_key


def _make_app(org_id: int = 42):
    app = FastAPI()
    app.include_router(router)
    app.include_router(public_router)
    mock_user = MagicMock()
    mock_user.selected_organization_id = org_id
    app.dependency_overrides[get_user] = lambda: mock_user
    return app


def _config_row(**kwargs):
    now = datetime.now(UTC)
    defaults = {
        "id": 1,
        "organization_id": 42,
        "name": "Primary",
        "gateway_provider_type": "custom",
        "is_enabled": True,
        "credentials": {
            "sip_host": "sip.example.com",
            "sip_port": 5060,
            "sip_username": "user",
            "sip_password": "topsecret",
            "sip_caller_id": "+15551234567",
            "telegram_destination_id": "@mybot",
            "gateway_api_base_url": "https://gateway.example.com/api",
        },
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


VALID_CREATE_BODY = {
    "name": "TG Gateway",
    "gateway_provider_type": "custom",
    "is_enabled": True,
    "credentials": {
        "sip_host": "sip.example.com",
        "sip_port": 5060,
        "sip_username": "user",
        "sip_password": "secret123",
        "sip_caller_id": "+15551234567",
        "telegram_destination_id": "@mybot",
        "gateway_api_base_url": "https://gateway.example.com/api",
    },
}


class TestTelegramSipGatewayRoutes:
    def test_metadata_lists_provider_types(self):
        client = TestClient(_make_app())
        res = client.get("/organizations/telegram-sip-gateway/metadata")
        assert res.status_code == 200
        data = res.json()
        assert "custom" in data["provider_types"]
        assert "Telegram does not support SIP" in data["description"]

    def test_create_masks_password_on_get(self):
        client = TestClient(_make_app())
        row = _config_row()

        with patch("api.routes.telegram_sip_gateway.db_client") as mock_db:
            mock_db.create_gateway_configuration = AsyncMock(return_value=row)
            create = client.post(
                "/organizations/telegram-sip-gateway/configs",
                json=VALID_CREATE_BODY,
            )
            assert create.status_code == 200
            assert "***" in create.json()["credentials"]["sip_password"]

            mock_db.get_gateway_configuration_for_org = AsyncMock(return_value=row)
            get_res = client.get("/organizations/telegram-sip-gateway/configs/1")
            assert get_res.status_code == 200
            assert get_res.json()["credentials"]["sip_password"] != "topsecret"

    def test_update_preserves_masked_password(self):
        client = TestClient(_make_app())
        existing = _config_row()

        with patch("api.routes.telegram_sip_gateway.db_client") as mock_db:
            mock_db.get_gateway_configuration_for_org = AsyncMock(return_value=existing)
            mock_db.update_gateway_configuration = AsyncMock(return_value=existing)

            res = client.put(
                "/organizations/telegram-sip-gateway/configs/1",
                json={
                    "credentials": {
                        **VALID_CREATE_BODY["credentials"],
                        "sip_password": mask_key("topsecret"),
                    }
                },
            )
            assert res.status_code == 200
            sent_credentials = mock_db.update_gateway_configuration.await_args.kwargs[
                "credentials"
            ]
            assert sent_credentials["sip_password"] == "topsecret"

    def test_create_rejects_missing_api_url(self):
        client = TestClient(_make_app())
        body = {**VALID_CREATE_BODY}
        body["credentials"] = {
            k: v
            for k, v in body["credentials"].items()
            if k != "gateway_api_base_url"
        }
        res = client.post("/organizations/telegram-sip-gateway/configs", json=body)
        assert res.status_code == 422

    def test_test_connection_endpoint(self):
        client = TestClient(_make_app())
        row = _config_row()

        with (
            patch("api.routes.telegram_sip_gateway.db_client") as mock_db,
            patch("api.routes.telegram_sip_gateway._service") as mock_service,
        ):
            mock_db.get_gateway_configuration_for_org = AsyncMock(return_value=row)
            mock_service.test_connection = AsyncMock(
                return_value={"ok": True, "message": "ok", "latency_ms": 12.5}
            )
            res = client.post("/organizations/telegram-sip-gateway/configs/1/test")
        assert res.status_code == 200
        assert res.json()["ok"] is True

    def test_public_status_webhook_without_auth(self):
        client = TestClient(_make_app())
        row = _config_row()
        call_log = SimpleNamespace(
            id=5,
            configuration_id=1,
            gateway_call_id="gw-1",
            direction="outbound",
            destination="@user",
            status="completed",
            error_code=None,
            error_message=None,
            events=[],
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

        with (
            patch("api.routes.telegram_sip_gateway.db_client") as mock_db,
            patch("api.routes.telegram_sip_gateway._service") as mock_service,
        ):
            mock_db.get_gateway_configuration = AsyncMock(return_value=row)
            mock_service.apply_status_webhook = AsyncMock(return_value=call_log)
            res = client.post(
                "/telegram-sip-gateway/webhooks/1/status",
                json={"call_id": "gw-1", "status": "completed"},
            )
        assert res.status_code == 200
        assert res.json()["status"] == "completed"

    def test_initiate_call_returns_gateway_error(self):
        client = TestClient(_make_app())
        row = _config_row()

        with (
            patch("api.routes.telegram_sip_gateway.db_client") as mock_db,
            patch("api.routes.telegram_sip_gateway._service") as mock_service,
        ):
            from api.services.telegram_sip.providers.custom import GatewayProviderError

            mock_db.get_gateway_configuration_for_org = AsyncMock(return_value=row)
            mock_service.initiate_call = AsyncMock(
                side_effect=GatewayProviderError("gateway_unavailable", "down")
            )
            res = client.post(
                "/organizations/telegram-sip-gateway/configs/1/calls",
                json={"destination": "@user"},
            )
        assert res.status_code == 502
        assert res.json()["detail"]["code"] == "gateway_unavailable"


@pytest.mark.asyncio
async def test_db_create_and_list_gateway(db_session):
    """Integration: persist gateway configuration via db client."""
    org, _ = await db_session.get_or_create_organization_by_provider_id(
        "tg_sip_test_org"
    )
    row = await db_session.create_gateway_configuration(
        organization_id=org.id,
        name="Test Gateway",
        gateway_provider_type="custom",
        credentials=VALID_CREATE_BODY["credentials"],
    )
    listed = await db_session.list_gateway_configurations(org.id)
    assert any(r.id == row.id for r in listed)
