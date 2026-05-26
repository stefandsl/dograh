"""Unit tests for the MessageNet telephony provider.

Scope:
* SIP URI parsing helper
* Config schemas (validators, username defaulting hint, sensitive field)
* Provider registration through ProviderSpec
* Provider methods that don't need a real SIP gateway (validate_config,
  get_available_phone_numbers, username fallback)
* SIP gateway abstraction (stub raises, override + reset, provider
  surfaces ``MessagenetGatewayNotConfigured`` as HTTP 503)
* Password never leaks through ``logger.info`` calls
* Schema discriminated-union round-trip

These tests use no DB fixtures, so they skip the session-scoped test-database
setup in ``api/conftest.py``. They still require ``api/.env.test`` (or the
equivalent env vars) to define ``DATABASE_URL`` and ``REDIS_URL`` because the
root conftest reads ``api.constants`` at import time.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.enums import WorkflowRunMode
from api.schemas.telephony_config import (
    MessagenetConfigurationRequest,
    MessagenetConfigurationResponse,
    TelephonyConfigurationResponse,
)
from api.services.telephony import registry
from api.services.telephony.providers.messagenet import SPEC
from api.services.telephony.providers.messagenet.provider import MessagenetProvider
from api.services.telephony.providers.messagenet.sip_gateway import (
    GatewayCallHandle,
    MessagenetGatewayNotConfigured,
    StubMessagenetSipGateway,
    get_sip_gateway,
    reset_sip_gateway,
    set_sip_gateway,
)
from api.services.telephony.providers.messagenet.sip_uri import (
    SipUriError,
    parse_sip_uri,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_REQUEST_PAYLOAD = {
    "provider": "messagenet",
    "sip_uri": "sip:5000000@sip.messagenet.it",
    "username": "5000000",
    "password": "s3cret-shh",
    "from_numbers": ["+390212345678"],
}


@pytest.fixture(autouse=True)
def _reset_gateway():
    """Each test starts with the default stub gateway."""
    reset_sip_gateway()
    yield
    reset_sip_gateway()


# ---------------------------------------------------------------------------
# SIP URI parsing
# ---------------------------------------------------------------------------


class TestSipUriParsing:
    def test_basic_sip(self):
        parsed = parse_sip_uri("sip:5000000@sip.messagenet.it")
        assert parsed.scheme == "sip"
        assert parsed.user == "5000000"
        assert parsed.host == "sip.messagenet.it"
        assert parsed.port is None

    def test_sips_with_port(self):
        parsed = parse_sip_uri("sips:alice@sip.example.com:5061")
        assert parsed.scheme == "sips"
        assert parsed.user == "alice"
        assert parsed.host == "sip.example.com"
        assert parsed.port == 5061

    def test_strips_params_and_headers(self):
        parsed = parse_sip_uri("sip:5000000@sip.messagenet.it;transport=tcp?subject=hi")
        assert parsed.host == "sip.messagenet.it"
        assert parsed.user == "5000000"

    def test_missing_user_raises(self):
        with pytest.raises(SipUriError):
            parse_sip_uri("sip:@sip.messagenet.it")

    def test_missing_host_raises(self):
        with pytest.raises(SipUriError):
            parse_sip_uri("sip:5000000@")

    def test_missing_at_sign_raises(self):
        with pytest.raises(SipUriError):
            parse_sip_uri("sip:sip.messagenet.it")

    def test_unsupported_scheme_raises(self):
        with pytest.raises(SipUriError):
            parse_sip_uri("http://sip.messagenet.it")

    def test_empty_raises(self):
        with pytest.raises(SipUriError):
            parse_sip_uri("")

    def test_bad_port_raises(self):
        with pytest.raises(SipUriError):
            parse_sip_uri("sip:user@host:notaport")

    def test_port_out_of_range_raises(self):
        with pytest.raises(SipUriError):
            parse_sip_uri("sip:user@host:70000")


# ---------------------------------------------------------------------------
# Config schemas
# ---------------------------------------------------------------------------


class TestConfigSchemas:
    def test_roundtrip_request(self):
        req = MessagenetConfigurationRequest(**_VALID_REQUEST_PAYLOAD)
        assert req.provider == "messagenet"
        assert req.sip_uri == "sip:5000000@sip.messagenet.it"
        assert req.username == "5000000"
        assert req.password == "s3cret-shh"
        assert req.from_numbers == ["+390212345678"]

    def test_default_provider_literal(self):
        # ``provider`` defaults so callers don't have to send it explicitly.
        payload = {**_VALID_REQUEST_PAYLOAD}
        payload.pop("provider")
        req = MessagenetConfigurationRequest(**payload)
        assert req.provider == "messagenet"

    def test_missing_sip_uri_fails(self):
        payload = {**_VALID_REQUEST_PAYLOAD}
        payload.pop("sip_uri")
        with pytest.raises(ValidationError):
            MessagenetConfigurationRequest(**payload)

    def test_missing_password_fails(self):
        payload = {**_VALID_REQUEST_PAYLOAD}
        payload.pop("password")
        with pytest.raises(ValidationError):
            MessagenetConfigurationRequest(**payload)

    def test_empty_password_fails(self):
        payload = {**_VALID_REQUEST_PAYLOAD, "password": ""}
        with pytest.raises(ValidationError):
            MessagenetConfigurationRequest(**payload)

    def test_invalid_sip_uri_fails(self):
        payload = {**_VALID_REQUEST_PAYLOAD, "sip_uri": "not-a-sip-uri"}
        with pytest.raises(ValidationError):
            MessagenetConfigurationRequest(**payload)

    def test_username_can_be_omitted(self):
        payload = {**_VALID_REQUEST_PAYLOAD}
        payload.pop("username")
        req = MessagenetConfigurationRequest(**payload)
        assert req.username is None  # provider derives at runtime

    def test_blank_username_becomes_none(self):
        # The provider treats both ``None`` and ``""`` as "use SIP URI default".
        payload = {**_VALID_REQUEST_PAYLOAD, "username": "   "}
        req = MessagenetConfigurationRequest(**payload)
        assert req.username is None

    def test_response_carries_provider_literal(self):
        resp = MessagenetConfigurationResponse(
            sip_uri="sip:5000000@sip.messagenet.it",
            username=None,
            password="***masked***",
            from_numbers=[],
        )
        assert resp.provider == "messagenet"


# ---------------------------------------------------------------------------
# Provider registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_spec_registered(self):
        assert registry.get("messagenet") is SPEC

    def test_spec_name_matches_workflow_run_mode(self):
        assert SPEC.name == WorkflowRunMode.MESSAGENET.value == "messagenet"

    def test_spec_uses_telephony_sample_rate(self):
        assert SPEC.transport_sample_rate == 8000

    def test_no_account_id_field(self):
        # MessageNet inbound is matched by called number, not account-id.
        assert SPEC.account_id_credential_field == ""

    def test_ui_metadata_has_required_fields(self):
        names = [f.name for f in SPEC.ui_metadata.fields]
        assert names == ["sip_uri", "username", "password", "from_numbers"]

    def test_password_marked_sensitive(self):
        password_field = next(
            f for f in SPEC.ui_metadata.fields if f.name == "password"
        )
        assert password_field.sensitive is True
        assert password_field.type == "password"

    def test_other_fields_not_sensitive(self):
        for field in SPEC.ui_metadata.fields:
            if field.name == "password":
                continue
            assert field.sensitive is False, f"{field.name} should not be sensitive"


# ---------------------------------------------------------------------------
# Provider behavior (without a live gateway)
# ---------------------------------------------------------------------------


def _build_provider(**overrides) -> MessagenetProvider:
    cfg = {
        "provider": "messagenet",
        "sip_uri": "sip:5000000@sip.messagenet.it",
        "username": None,
        "password": "s3cret-shh",
        "from_numbers": ["+390212345678"],
        **overrides,
    }
    return MessagenetProvider(cfg)


class TestProviderInit:
    def test_validate_config_ok(self):
        provider = _build_provider()
        assert provider.validate_config() is True

    def test_validate_config_missing_password(self):
        provider = _build_provider(password="")
        assert provider.validate_config() is False

    def test_validate_config_missing_sip_uri(self):
        provider = _build_provider(sip_uri="")
        assert provider.validate_config() is False

    def test_username_defaults_from_sip_uri(self):
        provider = _build_provider(username=None)
        assert provider.username == "5000000"

    def test_blank_username_defaults_from_sip_uri(self):
        provider = _build_provider(username="")
        assert provider.username == "5000000"

    def test_explicit_username_preserved(self):
        provider = _build_provider(username="my-explicit-user")
        assert provider.username == "my-explicit-user"

    def test_from_numbers_string_normalized_to_list(self):
        # Defensive: stored config might have come from a JSON column with a
        # bare string. The constructor should normalize it.
        provider = _build_provider(from_numbers="+390212345678")
        assert provider.from_numbers == ["+390212345678"]

    @pytest.mark.asyncio
    async def test_get_available_phone_numbers_returns_from_numbers(self):
        provider = _build_provider(from_numbers=["+1", "+2"])
        assert await provider.get_available_phone_numbers() == ["+1", "+2"]

    @pytest.mark.asyncio
    async def test_get_available_phone_numbers_returns_copy(self):
        # Callers should be free to mutate the returned list without
        # corrupting the provider's internal state.
        provider = _build_provider(from_numbers=["+1"])
        result = await provider.get_available_phone_numbers()
        result.append("+999")
        assert provider.from_numbers == ["+1"]


# ---------------------------------------------------------------------------
# SIP gateway abstraction
# ---------------------------------------------------------------------------


class TestSipGatewayStub:
    @pytest.mark.asyncio
    async def test_default_gateway_is_stub(self):
        gw = get_sip_gateway()
        assert isinstance(gw, StubMessagenetSipGateway)

    @pytest.mark.asyncio
    async def test_register_trunk_raises(self):
        gw = StubMessagenetSipGateway()
        with pytest.raises(MessagenetGatewayNotConfigured):
            await gw.register_trunk(MagicMock())

    @pytest.mark.asyncio
    async def test_originate_call_raises(self):
        gw = StubMessagenetSipGateway()
        with pytest.raises(MessagenetGatewayNotConfigured):
            await gw.originate_call(
                credentials=MagicMock(),
                to_number="+1",
                from_number=None,
                workflow_run_id=None,
            )

    @pytest.mark.asyncio
    async def test_hangup_raises(self):
        gw = StubMessagenetSipGateway()
        with pytest.raises(MessagenetGatewayNotConfigured):
            await gw.hangup("any-id")

    @pytest.mark.asyncio
    async def test_get_call_status_raises(self):
        gw = StubMessagenetSipGateway()
        with pytest.raises(MessagenetGatewayNotConfigured):
            await gw.get_call_status("any-id")

    def test_set_and_reset_gateway(self):
        custom = MagicMock()
        set_sip_gateway(custom)
        assert get_sip_gateway() is custom
        reset_sip_gateway()
        assert isinstance(get_sip_gateway(), StubMessagenetSipGateway)


# ---------------------------------------------------------------------------
# initiate_call behavior
# ---------------------------------------------------------------------------


class TestInitiateCall:
    @pytest.mark.asyncio
    async def test_initiate_call_503_when_gateway_not_configured(self):
        provider = _build_provider()
        with pytest.raises(HTTPException) as ei:
            await provider.initiate_call(to_number="+390212345678", webhook_url="")
        assert ei.value.status_code == 503
        assert "MessageNet SIP gateway is not configured" in ei.value.detail

    @pytest.mark.asyncio
    async def test_initiate_call_400_when_config_invalid(self):
        provider = _build_provider(password="")
        with pytest.raises(HTTPException) as ei:
            await provider.initiate_call(to_number="+390212345678", webhook_url="")
        assert ei.value.status_code == 400

    @pytest.mark.asyncio
    async def test_initiate_call_success_with_mocked_gateway(self):
        gateway = MagicMock()
        gateway.originate_call = AsyncMock(
            return_value=GatewayCallHandle(
                call_id="call-abc",
                status="originated",
                raw={"backend": "asterisk"},
            )
        )
        set_sip_gateway(gateway)

        provider = _build_provider()
        result = await provider.initiate_call(
            to_number="+390212345678",
            webhook_url="",
            workflow_run_id=42,
            from_number="+390299999999",
        )

        assert result.call_id == "call-abc"
        assert result.status == "originated"
        assert result.caller_number == "+390299999999"
        # The gateway was handed the typed credentials, not the raw dict.
        kwargs = gateway.originate_call.await_args.kwargs
        assert kwargs["to_number"] == "+390212345678"
        assert kwargs["from_number"] == "+390299999999"
        assert kwargs["workflow_run_id"] == 42
        creds = kwargs["credentials"]
        assert creds.sip_uri.host == "sip.messagenet.it"
        assert creds.username == "5000000"
        assert creds.password == "s3cret-shh"

    @pytest.mark.asyncio
    async def test_initiate_call_does_not_log_password(self):
        # Use a distinctive password so substring search has no false hits.
        secret = "tr0ub4dor&3-not-a-real-secret"
        provider = _build_provider(password=secret)

        captured: list[str] = []
        with patch(
            "api.services.telephony.providers.messagenet.provider.logger"
        ) as mock_logger:
            mock_logger.info.side_effect = lambda msg, *a, **kw: captured.append(
                str(msg)
            )
            mock_logger.warning.side_effect = lambda msg, *a, **kw: captured.append(
                str(msg)
            )
            mock_logger.debug.side_effect = lambda msg, *a, **kw: captured.append(
                str(msg)
            )
            mock_logger.error.side_effect = lambda msg, *a, **kw: captured.append(
                str(msg)
            )

            with pytest.raises(HTTPException):
                await provider.initiate_call(
                    to_number="+390212345678", webhook_url=""
                )

        # Sanity: we actually captured at least one log line.
        assert captured, "expected provider.initiate_call to log at least once"
        for line in captured:
            assert secret not in line, f"password leaked in log line: {line!r}"


# ---------------------------------------------------------------------------
# get_call_status
# ---------------------------------------------------------------------------


class TestGetCallStatus:
    @pytest.mark.asyncio
    async def test_get_call_status_503_when_gateway_not_configured(self):
        provider = _build_provider()
        with pytest.raises(HTTPException) as ei:
            await provider.get_call_status("call-abc")
        assert ei.value.status_code == 503

    @pytest.mark.asyncio
    async def test_get_call_status_passes_through_gateway_payload(self):
        gateway = MagicMock()
        gateway.get_call_status = AsyncMock(
            return_value={"call_id": "call-abc", "status": "answered"}
        )
        set_sip_gateway(gateway)

        provider = _build_provider()
        result = await provider.get_call_status("call-abc")

        assert result == {"call_id": "call-abc", "status": "answered"}
        gateway.get_call_status.assert_awaited_once_with("call-abc")


# ---------------------------------------------------------------------------
# Schema integration
# ---------------------------------------------------------------------------


class TestSchemaIntegration:
    def test_response_model_accepts_messagenet(self):
        resp = TelephonyConfigurationResponse(
            messagenet=MessagenetConfigurationResponse(
                sip_uri="sip:5000000@sip.messagenet.it",
                username="5000000",
                password="****",
                from_numbers=[],
            )
        )
        assert resp.messagenet is not None
        assert resp.messagenet.provider == "messagenet"

    def test_discriminated_union_dispatches_to_messagenet(self):
        # Pydantic must pick the MessagenetConfigurationRequest variant when
        # ``provider == "messagenet"``. Going through TypeAdapter mirrors how
        # FastAPI resolves the request body.
        from pydantic import TypeAdapter

        from api.schemas.telephony_config import TelephonyConfigRequest

        adapter = TypeAdapter(TelephonyConfigRequest)
        parsed = adapter.validate_python(_VALID_REQUEST_PAYLOAD)
        assert isinstance(parsed, MessagenetConfigurationRequest)


# ---------------------------------------------------------------------------
# Inbound surface (minimal)
# ---------------------------------------------------------------------------


class TestInboundSurface:
    def test_can_handle_webhook_false(self):
        # MessageNet inbound arrives over SIP, not HTTP webhooks.
        assert MessagenetProvider.can_handle_webhook({}, {}) is False

    def test_parse_inbound_webhook_normalizes(self):
        normalized = MessagenetProvider.parse_inbound_webhook(
            {
                "call_id": "call-xyz",
                "from_number": "+390212345678",
                "to_number": "+390299999999",
                "status": "ringing",
            }
        )
        assert normalized.provider == "messagenet"
        assert normalized.call_id == "call-xyz"
        assert normalized.direction == "inbound"
        assert normalized.from_number == "+390212345678"

    def test_validate_account_id_is_permissive(self):
        # No account-id matching on MessageNet — see SPEC.account_id_credential_field.
        assert (
            MessagenetProvider.validate_account_id({}, "anything-goes-here") is True
        )

    @pytest.mark.asyncio
    async def test_start_inbound_stream_returns_204(self):
        provider = _build_provider()
        resp = await provider.start_inbound_stream(
            websocket_url="wss://example",
            workflow_run_id=1,
            normalized_data=MessagenetProvider.parse_inbound_webhook({}),
            backend_endpoint="https://example",
        )
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Transfer surface (not supported in phase 1)
# ---------------------------------------------------------------------------


class TestTransferSurface:
    def test_supports_transfers_false(self):
        assert _build_provider().supports_transfers() is False

    @pytest.mark.asyncio
    async def test_transfer_call_raises_not_implemented(self):
        provider = _build_provider()
        with pytest.raises(NotImplementedError):
            await provider.transfer_call(
                destination="+1",
                transfer_id="t-1",
                conference_name="room",
            )
