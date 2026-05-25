"""Register SIP-to-Telegram gateway providers."""

from api.services.telegram_sip.providers.custom import CustomSipTelegramGatewayProvider
from api.services.telegram_sip.registry import register

# sip_tg and tg2sip use the same HTTP contract via configurable base URL.
for _provider_type in ("custom", "sip_tg", "tg2sip"):
    register(_provider_type, CustomSipTelegramGatewayProvider)
