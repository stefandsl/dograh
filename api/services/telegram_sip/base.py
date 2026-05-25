"""Provider abstraction for SIP-to-Telegram gateway integrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from api.services.telegram_sip.config import TelegramSipGatewayConfig


@dataclass
class GatewayValidationResult:
    ok: bool
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayConnectionTestResult:
    ok: bool
    message: str
    latency_ms: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayCallResult:
    call_id: str
    status: str
    provider_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayIncomingCallResult:
    routed: bool
    call_id: Optional[str] = None
    status: str = "ringing"
    message: Optional[str] = None
    provider_metadata: Dict[str, Any] = field(default_factory=dict)


class TelegramSipGatewayProvider(ABC):
    """Bridge between Dograh and an external SIP↔Telegram gateway."""

    PROVIDER_TYPE: str = ""

    @abstractmethod
    def validate_config(self, config: TelegramSipGatewayConfig) -> GatewayValidationResult:
        """Validate configuration fields before persisting."""

    @abstractmethod
    async def test_connection(
        self, config: TelegramSipGatewayConfig
    ) -> GatewayConnectionTestResult:
        """Probe gateway reachability and SIP credentials."""

    @abstractmethod
    async def initiate_call(
        self,
        config: TelegramSipGatewayConfig,
        destination: str,
        *,
        webhook_url: Optional[str] = None,
    ) -> GatewayCallResult:
        """Place an outbound call to a Telegram destination via the gateway."""

    @abstractmethod
    async def handle_incoming_call(
        self, config: TelegramSipGatewayConfig, payload: Dict[str, Any]
    ) -> GatewayIncomingCallResult:
        """Route an inbound SIP webhook to the configured Telegram destination."""

    @abstractmethod
    async def get_call_status(
        self, config: TelegramSipGatewayConfig, call_id: str
    ) -> Dict[str, Any]:
        """Fetch current call status from the gateway."""
