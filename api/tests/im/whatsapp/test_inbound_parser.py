"""Tests for ``inbound_parser.parse_webhook``.

The parser is pure — dict in, ``ParsedWebhook`` out — so these are
straightforward fixture-driven tests against a few realistic Meta
payload shapes.
"""

from __future__ import annotations

from api.services.im.whatsapp.inbound_parser import parse_webhook


def _envelope(value: dict) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [{"field": "messages", "value": value}],
            }
        ],
    }


def test_parses_text_message():
    payload = _envelope(
        {
            "messaging_product": "whatsapp",
            "metadata": {
                "display_phone_number": "393454717205",
                "phone_number_id": "PNID-123",
            },
            "contacts": [{"profile": {"name": "Stefan"}, "wa_id": "393450000000"}],
            "messages": [
                {
                    "from": "393450000000",
                    "id": "wamid.HBg",
                    "timestamp": "1717000000",
                    "type": "text",
                    "text": {"body": "Ciao Dograh"},
                }
            ],
        }
    )

    parsed = parse_webhook(payload)
    assert len(parsed.messages) == 1
    msg = parsed.messages[0]
    assert msg.channel_phone_number_id == "PNID-123"
    assert msg.wa_id == "393450000000"
    assert msg.message_id == "wamid.HBg"
    assert msg.message_type == "text"
    assert msg.text == "Ciao Dograh"
    assert msg.profile_name == "Stefan"
    assert msg.timestamp == 1717000000
    assert parsed.statuses == []


def test_parses_audio_message_as_media():
    payload = _envelope(
        {
            "messaging_product": "whatsapp",
            "metadata": {"phone_number_id": "PNID-123"},
            "messages": [
                {
                    "from": "393450000000",
                    "id": "wamid.audio",
                    "timestamp": "1717000000",
                    "type": "audio",
                    "audio": {
                        "id": "MEDIA-ID",
                        "mime_type": "audio/ogg; codecs=opus",
                        "sha256": "abc",
                    },
                }
            ],
        }
    )

    parsed = parse_webhook(payload)
    assert len(parsed.messages) == 1
    msg = parsed.messages[0]
    assert msg.message_type == "audio"
    assert msg.text is None
    assert msg.media == {
        "id": "MEDIA-ID",
        "mime_type": "audio/ogg; codecs=opus",
        "sha256": "abc",
        "caption": None,
    }


def test_parses_button_reply_as_text():
    payload = _envelope(
        {
            "messaging_product": "whatsapp",
            "metadata": {"phone_number_id": "PNID-123"},
            "messages": [
                {
                    "from": "393450000000",
                    "id": "wamid.btn",
                    "timestamp": "1717000000",
                    "type": "interactive",
                    "interactive": {
                        "type": "button_reply",
                        "button_reply": {"id": "yes_btn", "title": "Yes please"},
                    },
                }
            ],
        }
    )

    parsed = parse_webhook(payload)
    assert parsed.messages[0].text == "Yes please"
    assert parsed.messages[0].message_type == "interactive"


def test_parses_status_only_payload():
    payload = _envelope(
        {
            "messaging_product": "whatsapp",
            "metadata": {"phone_number_id": "PNID-123"},
            "statuses": [
                {
                    "id": "wamid.outbound.1",
                    "status": "delivered",
                    "timestamp": "1717000050",
                    "recipient_id": "393450000000",
                }
            ],
        }
    )

    parsed = parse_webhook(payload)
    assert parsed.messages == []
    assert len(parsed.statuses) == 1
    st = parsed.statuses[0]
    assert st.status == "delivered"
    assert st.recipient_id == "393450000000"


def test_handles_unknown_message_type_gracefully():
    payload = _envelope(
        {
            "messaging_product": "whatsapp",
            "metadata": {"phone_number_id": "PNID-123"},
            "messages": [
                {
                    "from": "393450000000",
                    "id": "wamid.weird",
                    "timestamp": "1717000000",
                    "type": "location",  # not in our extractor list
                    "location": {"latitude": 45.0, "longitude": 9.0},
                }
            ],
        }
    )

    parsed = parse_webhook(payload)
    assert len(parsed.messages) == 1
    msg = parsed.messages[0]
    assert msg.message_type == "location"
    assert msg.text is None
    assert msg.media is None
    # raw is preserved for the dispatcher / audit log
    assert msg.raw.get("location", {}).get("latitude") == 45.0


def test_returns_empty_for_wrong_object():
    parsed = parse_webhook({"object": "instagram", "entry": []})
    assert parsed.messages == [] and parsed.statuses == []


def test_returns_empty_for_garbage_input():
    parsed = parse_webhook({})
    assert parsed.messages == [] and parsed.statuses == []
    parsed = parse_webhook(None)  # type: ignore[arg-type]
    assert parsed.messages == [] and parsed.statuses == []
