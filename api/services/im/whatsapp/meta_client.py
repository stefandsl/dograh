"""Meta WhatsApp Cloud API outbound client.

Tiny wrapper around the Graph API messaging endpoint. Each call takes a
``WhatsAppChannelConfig``-shaped dict (decrypted from the channel row)
plus its arguments and returns the parsed JSON response. HTTP errors are
re-raised as ``MetaClientError`` with the status code and Meta's error
payload — the caller (webhook dispatcher) is expected to log and either
fall through or escalate.

The Graph API URL is built per-call from ``graph_version`` +
``phone_number_id`` rather than baked in, so different channels can sit
on different Graph versions while the same image is running.

No logging of the access token (or the body where it could be echoed).
"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger


class MetaClientError(Exception):
    """Raised when Meta returns a non-2xx response.

    Attributes:
        status_code: The HTTP status from Meta.
        meta_error: Meta's ``error`` field from the JSON response if
            available; ``None`` otherwise.
    """

    def __init__(
        self, status_code: int, meta_error: dict[str, Any] | None, message: str
    ):
        super().__init__(message)
        self.status_code = status_code
        self.meta_error = meta_error


def _base_url(config: dict[str, Any]) -> str:
    version = config.get("graph_version") or "v20.0"
    phone_number_id = config["phone_number_id"]
    return f"https://graph.facebook.com/{version}/{phone_number_id}/messages"


def _auth_headers(config: dict[str, Any]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config['access_token']}",
        "Content-Type": "application/json",
    }


async def _post(config: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    url = _base_url(config)
    headers = _auth_headers(config)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=body, headers=headers)

    if resp.status_code >= 400:
        meta_error: dict[str, Any] | None = None
        try:
            meta_error = resp.json().get("error")
        except Exception:
            meta_error = None
        # Log the failure with the Meta error fields but NEVER the body
        # we sent — it may carry an access token if a future caller adds
        # one to the payload by mistake.
        logger.warning(
            "[whatsapp/meta] outbound {status} url={url} meta_error={err}",
            status=resp.status_code,
            url=url,
            err=meta_error,
        )
        raise MetaClientError(
            status_code=resp.status_code,
            meta_error=meta_error,
            message=f"Meta returned {resp.status_code}",
        )

    return resp.json()


async def send_text(
    *, config: dict[str, Any], to: str, text: str, preview_url: bool = False
) -> dict[str, Any]:
    """Send a free-form text message.

    Only valid within Meta's 24-hour customer service window — outside
    it, Meta will reject with a ``131047`` error and the caller must
    use ``send_template`` instead.

    Args:
        config: Decrypted WhatsApp channel config (``phone_number_id``,
            ``access_token``, ``graph_version``).
        to: Recipient phone number in E.164 *without* the leading ``+``.
        text: Body. Meta enforces a 4096-character cap.
        preview_url: Whether Meta should render a link preview when the
            body contains a URL. Defaults to off.

    Returns:
        Parsed Meta response — useful fields: ``messages[0].id``.
    """
    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": text, "preview_url": preview_url},
    }
    return await _post(config, body)


async def send_template(
    *,
    config: dict[str, Any],
    to: str,
    template_name: str,
    language: str,
    variables: list[str] | None = None,
) -> dict[str, Any]:
    """Send a pre-approved template message.

    Used outside the 24-hour customer service window, and for marketing
    / utility / authentication categories. Template approval happens in
    Meta Business Manager — this function only fires the send.

    Args:
        config: Decrypted channel config.
        to: Recipient E.164 sans ``+``.
        template_name: The template's name as approved in Meta Business
            Manager.
        language: BCP-47 language code matching an approved translation
            (e.g. ``"en_US"``, ``"it"``).
        variables: Positional body-parameter substitutions. Pass an
            empty list (or ``None``) for templates with no variables.
    """
    components: list[dict[str, Any]] = []
    if variables:
        components.append(
            {
                "type": "body",
                "parameters": [{"type": "text", "text": v} for v in variables],
            }
        )
    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": components,
        },
    }
    return await _post(config, body)


async def send_media(
    *,
    config: dict[str, Any],
    to: str,
    media_type: str,
    media_id: str | None = None,
    media_url: str | None = None,
    caption: str | None = None,
) -> dict[str, Any]:
    """Send an image / audio / video / document reply.

    Exactly one of ``media_id`` (a Meta-hosted upload) or ``media_url``
    (a public HTTPS URL Meta will fetch) must be supplied.

    Args:
        config: Decrypted channel config.
        to: Recipient E.164 sans ``+``.
        media_type: ``"image" | "audio" | "video" | "document"``.
        media_id: A previously uploaded media ID. Mutually exclusive with
            ``media_url``.
        media_url: A public HTTPS URL Meta can pull from. Mutually
            exclusive with ``media_id``.
        caption: Optional caption (image/video/document only — audio
            ignores it).
    """
    if (media_id is None) == (media_url is None):
        raise ValueError("Provide exactly one of media_id or media_url")
    media_obj: dict[str, Any] = {}
    if media_id is not None:
        media_obj["id"] = media_id
    if media_url is not None:
        media_obj["link"] = media_url
    if caption and media_type in {"image", "video", "document"}:
        media_obj["caption"] = caption
    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": media_type,
        media_type: media_obj,
    }
    return await _post(config, body)


async def mark_as_read(*, config: dict[str, Any], message_id: str) -> dict[str, Any]:
    """Mark an inbound message as read (the blue double-tick).

    Best-effort. Errors are logged and swallowed by the caller; not
    delivering the read receipt is never a reason to fail the webhook
    response.
    """
    body = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    return await _post(config, body)
