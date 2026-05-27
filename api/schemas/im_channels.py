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
