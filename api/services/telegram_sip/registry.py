"""Registry for SIP-to-Telegram gateway provider implementations."""

from __future__ import annotations

from typing import Dict, Optional, Type

from api.services.telegram_sip.base import TelegramSipGatewayProvider

_REGISTRY: Dict[str, Type[TelegramSipGatewayProvider]] = {}


def register(provider_type: str, cls: Type[TelegramSipGatewayProvider]) -> None:
    if provider_type in _REGISTRY and _REGISTRY[provider_type] is not cls:
        raise ValueError(f"Gateway provider '{provider_type}' already registered")
    _REGISTRY[provider_type] = cls


def get(provider_type: str) -> TelegramSipGatewayProvider:
    try:
        cls = _REGISTRY[provider_type]
    except KeyError:
        raise ValueError(f"Unknown Telegram SIP gateway provider: {provider_type}") from None
    return cls()


def get_optional(provider_type: str) -> Optional[TelegramSipGatewayProvider]:
    cls = _REGISTRY.get(provider_type)
    return cls() if cls else None


def registered_types() -> list[str]:
    return sorted(_REGISTRY)
