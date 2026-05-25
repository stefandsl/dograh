"""SIP-to-Telegram gateway integration.

Telegram does not support SIP directly. Use an external gateway provider and
configure it via :class:`api.services.telegram_sip.service.TelegramSipService`.
"""

__all__ = ["TelegramSipService"]


def __getattr__(name: str):
    if name == "TelegramSipService":
        from api.services.telegram_sip.service import TelegramSipService

        return TelegramSipService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
