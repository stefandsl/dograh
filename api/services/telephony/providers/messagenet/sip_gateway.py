"""Abstraction over the SIP/media gateway that bridges Dograh ↔ MessageNet.

MessageNet exposes a SIP trunk (signalling + RTP), not a REST call-control
API like Twilio/Telnyx. To originate or accept calls from Dograh we need
a SIP-speaking media gateway sitting between the Dograh pipecat pipeline
(WebSocket audio) and MessageNet (SIP/RTP). In practice that gateway will
be Asterisk/PJSIP, Kamailio, or a similar component — provisioned per
deployment, *not* per Dograh organization.

This module defines:

* ``MessagenetSipGatewayClient`` — the protocol the provider depends on.
* ``MessagenetGatewayNotConfigured`` — the specific failure the provider
  surfaces back to the API as a 503 when no live gateway is wired up.
* ``StubMessagenetSipGateway`` — the default no-op implementation. It
  refuses every operation with ``MessagenetGatewayNotConfigured`` so the
  provider is safe to ship without a real backend.
* ``get_sip_gateway()`` — the indirection point. The real Asterisk-backed
  implementation can later replace the stub here without touching provider
  code.

Keeping this boundary clean means the provider never imports a SIP stack
directly; SIP/RTP code lives behind ``MessagenetSipGatewayClient``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from .sip_uri import ParsedSipUri


@dataclass(frozen=True)
class MessagenetTrunkCredentials:
    """Per-organization MessageNet SIP trunk credentials.

    Mirrors the stored config row but in a typed shape the gateway can
    consume without learning the Dograh dict layout.
    """

    sip_uri: ParsedSipUri
    username: str
    password: str  # Sensitive — never log this field
    from_numbers: List[str]


@dataclass(frozen=True)
class GatewayCallHandle:
    """Reference to a call the gateway has originated.

    ``call_id`` is whatever opaque identifier the backing gateway returns
    (Asterisk channel id, Kamailio dialog id, etc.). Treat it as opaque —
    the provider only forwards it back to the user.
    """

    call_id: str
    status: str  # e.g. "originated", "ringing"
    raw: Dict[str, Any]


class MessagenetGatewayNotConfigured(RuntimeError):
    """No live SIP/media gateway is configured for this deployment.

    Raised by every method on ``StubMessagenetSipGateway``. The provider
    catches it and re-raises as an HTTP 503 so the operator sees a clear
    message instead of a stack trace.
    """


class MessagenetSipGatewayClient(Protocol):
    """Protocol for the SIP/media gateway client.

    Implementations are deployment-level (one per Dograh server, not per
    org). The provider holds a reference obtained from ``get_sip_gateway()``
    and calls into it; SIP/RTP plumbing stays behind this protocol.
    """

    async def register_trunk(
        self, credentials: MessagenetTrunkCredentials
    ) -> None: ...

    async def originate_call(
        self,
        *,
        credentials: MessagenetTrunkCredentials,
        to_number: str,
        from_number: Optional[str],
        workflow_run_id: Optional[int],
        workflow_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> GatewayCallHandle: ...

    async def accept_inbound_call(self, call_id: str) -> None: ...

    async def hangup(self, call_id: str) -> None: ...

    async def get_call_status(self, call_id: str) -> Dict[str, Any]: ...


class StubMessagenetSipGateway:
    """Default gateway implementation. Always raises ``MessagenetGatewayNotConfigured``.

    Ships with the provider so the package is importable and registerable
    without a SIP backend present. Replace with a real Asterisk/PJSIP/
    Kamailio implementation by overriding ``get_sip_gateway()`` (or by
    injecting via a future config hook) — *do not* extend this class with
    real behavior; keep stubs and real backends separate.
    """

    _MESSAGE = (
        "MessageNet SIP gateway is not configured for this deployment. "
        "Wire a SIP/media gateway (e.g. Asterisk) and override "
        "messagenet.sip_gateway.get_sip_gateway() to return a real client."
    )

    async def register_trunk(self, credentials: MessagenetTrunkCredentials) -> None:
        raise MessagenetGatewayNotConfigured(self._MESSAGE)

    async def originate_call(
        self,
        *,
        credentials: MessagenetTrunkCredentials,
        to_number: str,
        from_number: Optional[str],
        workflow_run_id: Optional[int],
        workflow_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> GatewayCallHandle:
        raise MessagenetGatewayNotConfigured(self._MESSAGE)

    async def accept_inbound_call(self, call_id: str) -> None:
        raise MessagenetGatewayNotConfigured(self._MESSAGE)

    async def hangup(self, call_id: str) -> None:
        raise MessagenetGatewayNotConfigured(self._MESSAGE)

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        raise MessagenetGatewayNotConfigured(self._MESSAGE)


_gateway_singleton: Optional[MessagenetSipGatewayClient] = None


def get_sip_gateway() -> MessagenetSipGatewayClient:
    """Return the SIP gateway client to use for this deployment.

    Today this always returns the stub; the indirection exists so a real
    backend can be wired in by overwriting ``_gateway_singleton`` from a
    startup hook (or by rebinding this function in tests).
    """
    global _gateway_singleton
    if _gateway_singleton is None:
        _gateway_singleton = StubMessagenetSipGateway()
    return _gateway_singleton


def set_sip_gateway(client: MessagenetSipGatewayClient) -> None:
    """Override the gateway client (used by tests and future production wiring)."""
    global _gateway_singleton
    _gateway_singleton = client


def reset_sip_gateway() -> None:
    """Clear the singleton so the next ``get_sip_gateway()`` rebuilds the stub."""
    global _gateway_singleton
    _gateway_singleton = None
