"""WhatsApp Cloud API channel.

Inbound: Meta webhook (verified via HMAC-SHA256 of the raw body using
each channel's app_secret) → parse → dedupe → forward to workflow text
chat → reply via outbound HTTP.

Outbound: thin Meta Graph API client. ``send_text`` for free-form
replies within Meta's 24-hour customer service window; ``send_template``
for pre-approved templates outside it; ``send_media`` for media replies.

Credentials and verify_token live encrypted on ``im_channels`` (type
``'whatsapp'``) — see ``api/services/im/channel_service.py``. Nothing
in this package reads from environment variables; everything is per
channel row so multi-tenant deployments can host many WhatsApp accounts
side-by-side.
"""

from api.services.im.whatsapp.meta_client import (
    MetaClientError,
    send_media,
    send_template,
    send_text,
)
from api.services.im.whatsapp.signature import verify_signature

__all__ = [
    "MetaClientError",
    "send_media",
    "send_template",
    "send_text",
    "verify_signature",
]
