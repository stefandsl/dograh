"""Configuration models for SIP-to-Telegram gateway integrations.

Telegram does not support SIP natively. These settings target an external gateway
provider (SIP.TG, tg2sip, or a custom REST/SIP bridge) that bridges SIP and Telegram.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

GatewayProviderType = Literal["sip_tg", "tg2sip", "custom"]

SENSITIVE_CREDENTIAL_FIELDS = frozenset({"sip_password", "gateway_api_key"})


class TelegramSipGatewayCredentials(BaseModel):
    """Stored credential payload for a gateway configuration."""

    sip_host: str = Field(..., min_length=1, max_length=255)
    sip_port: int = Field(default=5060, ge=1, le=65535)
    sip_username: str = Field(..., min_length=1, max_length=128)
    sip_password: str = Field(..., min_length=1)
    sip_caller_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="SIP number or caller ID presented to the gateway",
    )
    telegram_destination_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Telegram account or routing ID understood by the gateway",
    )
    webhook_callback_url: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Optional callback URL registered with the gateway for call events",
    )
    gateway_api_base_url: Optional[str] = Field(
        default=None,
        max_length=512,
        description="REST API base URL for custom gateways (required when provider is custom)",
    )
    gateway_api_key: Optional[str] = Field(
        default=None,
        description="Optional API key for custom gateway REST authentication",
    )

    @field_validator("gateway_api_base_url", "webhook_callback_url")
    @classmethod
    def strip_optional_urls(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None


class TelegramSipGatewayConfig(BaseModel):
    """Full gateway configuration passed to providers."""

    gateway_provider_type: GatewayProviderType
    credentials: TelegramSipGatewayCredentials
