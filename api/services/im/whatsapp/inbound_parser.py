"""Parse Meta Cloud API webhook payloads into a normalised inbound shape.

Meta's payload is a deeply-nested envelope:

    { object: "whatsapp_business_account",
      entry: [ { id, changes: [ { field, value: { messaging_product,
                                                 metadata: { phone_number_id, display_phone_number },
                                                 contacts: [...],
                                                 messages: [...],
                                                 statuses: [...] } } ] } ] }

A single POST may carry multiple ``entry`` items, multiple ``changes``,
and a mix of messages and statuses. We flatten to a list of
``InboundMessage`` and a list of ``DeliveryStatus`` so the dispatcher
can iterate without worrying about Meta's envelope shape.

Statuses (``sent``/``delivered``/``read``/``failed``) are surfaced for
audit logging but do not currently drive any action — the dispatcher
ignores them. They are returned as a separate list so future code can
persist them without re-parsing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InboundMessage:
    """One inbound WhatsApp message, normalised."""

    # The Meta phone_number_id of the *channel* (us), used to look up
    # which im_channels row owns this message.
    channel_phone_number_id: str
    # The sender's E.164 (no leading +) — what we store as wa_id.
    wa_id: str
    # Meta message id; used for dedupe.
    message_id: str
    # "text" | "audio" | "image" | "video" | "document" | "sticker" |
    # "location" | "contacts" | "interactive" | "button" | "unsupported"
    message_type: str
    # Unix epoch seconds at which Meta received the message.
    timestamp: int
    # Plaintext body for type="text"; the rendered button label for
    # interactive replies. None for media.
    text: str | None = None
    # For media messages: { id, mime_type, sha256, caption? }. Caller
    # downloads via GET https://graph.facebook.com/<ver>/<id>.
    media: dict[str, Any] | None = None
    # The contact's profile name if Meta included it.
    profile_name: str | None = None
    # Raw value blob for fields we didn't extract — preserved so the
    # dispatcher can persist the full payload for audit without doing
    # its own parsing.
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryStatus:
    """One outbound delivery-status update."""

    channel_phone_number_id: str
    message_id: str
    status: str  # "sent" | "delivered" | "read" | "failed"
    timestamp: int
    recipient_id: str | None = None
    errors: list[dict[str, Any]] | None = None


@dataclass
class ParsedWebhook:
    messages: list[InboundMessage]
    statuses: list[DeliveryStatus]


def parse_webhook(payload: dict[str, Any]) -> ParsedWebhook:
    """Flatten a Meta webhook envelope into normalised lists.

    Robust to:
    - empty/missing entry, changes, messages, statuses
    - unknown change fields (only ``messages`` is processed)
    - unknown message types (recorded with type="unsupported" so the
      dispatcher can ack the webhook and optionally reply with a
      "I can only handle text" hint)

    Never raises on a well-formed-but-uninteresting payload.
    """
    messages: list[InboundMessage] = []
    statuses: list[DeliveryStatus] = []

    if not isinstance(payload, dict):
        return ParsedWebhook(messages, statuses)
    if payload.get("object") != "whatsapp_business_account":
        return ParsedWebhook(messages, statuses)

    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            if change.get("field") != "messages":
                continue
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            channel_pnid = str(metadata.get("phone_number_id") or "")
            contacts_by_wa = {
                c.get("wa_id"): c
                for c in (value.get("contacts") or [])
                if isinstance(c, dict)
            }

            for msg in value.get("messages") or []:
                if not isinstance(msg, dict):
                    continue
                wa_id = str(msg.get("from") or "")
                msg_id = str(msg.get("id") or "")
                msg_type = str(msg.get("type") or "unsupported")
                ts_raw = msg.get("timestamp") or 0
                try:
                    ts = int(ts_raw)
                except (TypeError, ValueError):
                    ts = 0

                text: str | None = None
                media: dict[str, Any] | None = None

                if msg_type == "text":
                    text = ((msg.get("text") or {}).get("body")) or ""
                elif msg_type in {"image", "audio", "video", "document", "sticker"}:
                    media_obj = msg.get(msg_type) or {}
                    media = {
                        "id": media_obj.get("id"),
                        "mime_type": media_obj.get("mime_type"),
                        "sha256": media_obj.get("sha256"),
                        "caption": media_obj.get("caption"),
                    }
                elif msg_type == "interactive":
                    # button reply or list reply
                    inter = msg.get("interactive") or {}
                    inter_type = inter.get("type")
                    if inter_type == "button_reply":
                        text = (inter.get("button_reply") or {}).get("title")
                    elif inter_type == "list_reply":
                        text = (inter.get("list_reply") or {}).get("title")
                elif msg_type == "button":
                    text = (msg.get("button") or {}).get("text")
                # else: leave text/media empty, keep raw for inspection

                profile_name: str | None = None
                contact = contacts_by_wa.get(wa_id)
                if contact:
                    profile = contact.get("profile") or {}
                    profile_name = profile.get("name")

                messages.append(
                    InboundMessage(
                        channel_phone_number_id=channel_pnid,
                        wa_id=wa_id,
                        message_id=msg_id,
                        message_type=msg_type,
                        timestamp=ts,
                        text=text,
                        media=media,
                        profile_name=profile_name,
                        raw=msg,
                    )
                )

            for st in value.get("statuses") or []:
                if not isinstance(st, dict):
                    continue
                try:
                    ts_st = int(st.get("timestamp") or 0)
                except (TypeError, ValueError):
                    ts_st = 0
                statuses.append(
                    DeliveryStatus(
                        channel_phone_number_id=channel_pnid,
                        message_id=str(st.get("id") or ""),
                        status=str(st.get("status") or ""),
                        timestamp=ts_st,
                        recipient_id=st.get("recipient_id"),
                        errors=st.get("errors"),
                    )
                )

    return ParsedWebhook(messages, statuses)
