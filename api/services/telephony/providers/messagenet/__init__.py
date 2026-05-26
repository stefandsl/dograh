"""MessageNet SIP-trunk telephony provider package.

Self-registers a ``ProviderSpec`` at import time so the rest of the
platform (factory, audio config, telephony config UI) picks it up via
the registry. SIP/RTP handling is intentionally pushed behind
``sip_gateway.MessagenetSipGatewayClient`` — see that module for the
abstraction boundary.
"""

from typing import Any, Dict

from api.services.telephony.registry import (
    ProviderSpec,
    ProviderUIField,
    ProviderUIMetadata,
    register,
)

from .config import MessagenetConfigurationRequest, MessagenetConfigurationResponse
from .provider import MessagenetProvider
from .sip_uri import SipUriError, parse_sip_uri
from .transport import create_transport


def _config_loader(value: Dict[str, Any]) -> Dict[str, Any]:
    """Reshape the JSONB credentials row into the provider's constructor dict.

    Pure dict reshaping per the providers AGENTS.md — no I/O. The factory
    layer attaches ``from_numbers`` from the joined phone-numbers table
    after this runs, so we don't pull it from credentials.

    Username defaulting is delegated to the provider's ``__init__`` so
    both stored configs and ad-hoc dicts (tests, future agent-stream
    flows) get the same treatment.
    """
    return {
        "provider": "messagenet",
        "sip_uri": value.get("sip_uri"),
        "username": value.get("username"),
        "password": value.get("password"),
        # ``from_numbers`` left unset on purpose — see comment above.
    }


_UI_METADATA = ProviderUIMetadata(
    display_name="MessageNet",
    docs_url="https://docs.dograh.com/integrations/telephony/messagenet",
    fields=[
        ProviderUIField(
            name="sip_uri",
            label="SIP URI",
            type="text",
            required=True,
            sensitive=False,
            description="MessageNet trunk SIP URI (e.g. sip:5000000@sip.messagenet.it).",
            placeholder="sip:5000000@sip.messagenet.it",
        ),
        ProviderUIField(
            name="username",
            label="SIP Username",
            type="text",
            required=False,
            sensitive=False,
            description="SIP auth username. Defaults to the SIP URI user part if left empty.",
        ),
        ProviderUIField(
            name="password",
            label="SIP Password",
            type="password",
            required=True,
            sensitive=True,
            description="MessageNet SIP password — masked on read.",
        ),
        ProviderUIField(
            name="from_numbers",
            label="Caller IDs",
            type="string-array",
            required=False,
            sensitive=False,
            description="Caller IDs / DIDs allowed for outbound calls.",
        ),
    ],
)


SPEC = ProviderSpec(
    name="messagenet",
    provider_cls=MessagenetProvider,
    config_loader=_config_loader,
    transport_factory=create_transport,
    transport_sample_rate=8000,
    config_request_cls=MessagenetConfigurationRequest,
    config_response_cls=MessagenetConfigurationResponse,
    ui_metadata=_UI_METADATA,
    # MessageNet inbound is routed by the called number on the SIP gateway
    # side, not by an account-id header on a webhook payload. Empty string
    # tells the dispatcher there's nothing to match on.
    account_id_credential_field="",
)


register(SPEC)


__all__ = [
    "SPEC",
    "MessagenetConfigurationRequest",
    "MessagenetConfigurationResponse",
    "MessagenetProvider",
    "create_transport",
    "parse_sip_uri",
    "SipUriError",
]
