"""Pydantic models for the IM channels API."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class TelegramChannelCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    bot_token: str = Field(..., min_length=10)
    allowed_user_ids: list[int] = Field(default_factory=list)
    enabled: bool = True


class TelegramChannelUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    bot_token: Optional[str] = Field(None, min_length=10)
    allowed_user_ids: Optional[list[int]] = None
    enabled: Optional[bool] = None


class TelegramChannelResponse(BaseModel):
    id: int
    type: Literal["telegram"] = "telegram"
    name: str
    enabled: bool
    api_key_id: Optional[int] = None
    # Token is masked to last 6 chars by the service before serialization.
    config: dict[str, Any]


class TelegramChannelCreateResponse(TelegramChannelResponse):
    """Includes the raw API key — only returned at creation/rotation."""

    api_key: str


class TelegramTestResponse(BaseModel):
    ok: bool
    username: Optional[str] = None
    bot_id: Optional[int] = None
    first_name: Optional[str] = None
    error: Optional[str] = None


class SecretBundleEntry(BaseModel):
    id: int
    organization_id: int
    name: str
    bot_token: str
    api_key: str
    allowed_user_ids: list[int] = Field(default_factory=list)


# --- WhatsApp Cloud API channel ------------------------------------------
class WhatsAppChannelCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    # Meta phone number id (a numeric string from the WhatsApp Business
    # Manager — distinct from the human-readable phone number).
    phone_number_id: str = Field(..., min_length=1, max_length=64)
    # Meta access token (system user, long-lived). Stored encrypted.
    access_token: str = Field(..., min_length=10)
    # Meta App Secret — used to verify x-hub-signature-256 on inbound
    # webhooks.
    app_secret: str = Field(..., min_length=8)
    # Verify token chosen at Meta Developer Console webhook subscription
    # time; we echo this back on GET /webhook to complete the handshake.
    verify_token: str = Field(..., min_length=4, max_length=128)
    business_account_id: Optional[str] = Field(None, max_length=64)
    graph_version: str = Field(default="v20.0", max_length=8)
    enabled: bool = True


class WhatsAppChannelUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    phone_number_id: Optional[str] = Field(None, min_length=1, max_length=64)
    access_token: Optional[str] = Field(None, min_length=10)
    app_secret: Optional[str] = Field(None, min_length=8)
    verify_token: Optional[str] = Field(None, min_length=4, max_length=128)
    business_account_id: Optional[str] = Field(None, max_length=64)
    graph_version: Optional[str] = Field(None, max_length=8)
    enabled: Optional[bool] = None


class WhatsAppChannelResponse(BaseModel):
    id: int
    type: Literal["whatsapp"] = "whatsapp"
    name: str
    enabled: bool
    # All secrets in ``config`` are masked to last 6 chars by the service
    # layer before serialization — phone_number_id, business_account_id,
    # and graph_version stay plaintext.
    config: dict[str, Any]


class WhatsAppTestResponse(BaseModel):
    ok: bool
    phone_number: Optional[str] = None
    verified_name: Optional[str] = None
    error: Optional[str] = None
