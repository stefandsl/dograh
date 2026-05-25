"""API schemas for Telegram SIP gateway configuration and calls."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

GatewayProviderType = Literal["sip_tg", "tg2sip", "custom"]


class TelegramSipGatewayCredentialsRequest(BaseModel):
    sip_host: str = Field(..., min_length=1, max_length=255)
    sip_port: int = Field(default=5060, ge=1, le=65535)
    sip_username: str = Field(..., min_length=1, max_length=128)
    sip_password: str = Field(..., min_length=1)
    sip_caller_id: str = Field(..., min_length=1, max_length=64)
    telegram_destination_id: str = Field(..., min_length=1, max_length=128)
    webhook_callback_url: Optional[str] = Field(default=None, max_length=512)
    gateway_api_base_url: Optional[str] = Field(default=None, max_length=512)
    gateway_api_key: Optional[str] = None


class TelegramSipGatewayCredentialsResponse(BaseModel):
    sip_host: str
    sip_port: int
    sip_username: str
    sip_password: str
    sip_caller_id: str
    telegram_destination_id: str
    webhook_callback_url: Optional[str] = None
    gateway_api_base_url: Optional[str] = None
    gateway_api_key: Optional[str] = None


class TelegramSipGatewayConfigCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    gateway_provider_type: GatewayProviderType
    credentials: TelegramSipGatewayCredentialsRequest
    is_enabled: bool = True


class TelegramSipGatewayConfigUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    gateway_provider_type: Optional[GatewayProviderType] = None
    credentials: Optional[TelegramSipGatewayCredentialsRequest] = None
    is_enabled: Optional[bool] = None


class TelegramSipGatewayConfigListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    gateway_provider_type: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class TelegramSipGatewayConfigDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    gateway_provider_type: str
    is_enabled: bool
    credentials: TelegramSipGatewayCredentialsResponse
    created_at: datetime
    updated_at: datetime


class TelegramSipGatewayConfigListResponse(BaseModel):
    configurations: List[TelegramSipGatewayConfigListItem]


class TelegramSipGatewayTestResponse(BaseModel):
    ok: bool
    message: str
    latency_ms: Optional[float] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class TelegramSipInitiateCallRequest(BaseModel):
    destination: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Telegram username, phone, or routing ID accepted by the gateway",
    )
    webhook_url: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Override callback URL for this call",
    )


class TelegramSipCallLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    configuration_id: int
    gateway_call_id: Optional[str] = None
    direction: str
    destination: str
    status: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    events: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TelegramSipCallLogListResponse(BaseModel):
    call_logs: List[TelegramSipCallLogResponse]


class TelegramSipProviderMetadataField(BaseModel):
    name: str
    label: str
    type: str
    required: bool = True
    sensitive: bool = False
    description: Optional[str] = None


class TelegramSipProvidersMetadataResponse(BaseModel):
    """UI form metadata for the Telegram SIP Gateway configuration screen."""

    provider_types: List[str]
    fields: List[TelegramSipProviderMetadataField]
    description: str = (
        "Telegram does not support SIP natively. Configure an external SIP↔Telegram "
        "gateway (e.g. SIP.TG, tg2sip, or a custom REST bridge) to place and receive calls."
    )
