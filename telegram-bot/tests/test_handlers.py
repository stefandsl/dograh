"""Unit tests for the menu handlers' pure helpers.

The full handler bodies require a live aiogram + DB and run under the
e2e suite (Phase 8). Here we cover ``_pick_assistant_text`` which is
the trickiest pure function — it walks the workflow_run text-chat
session_data shape (cursor-trimmed turns, ``assistant_message.text``
extraction) and decides what to show the user.
"""

from bot.handlers import _pick_assistant_text


def test_returns_placeholder_when_no_turns():
    payload = {"session_data": {}}
    assert "no assistant reply yet" in _pick_assistant_text(payload).lower()


def test_returns_last_assistant_text():
    payload = {
        "session_data": {
            "turns": [
                {"id": "t1", "assistant_message": {"text": "hi"}},
                {"id": "t2", "assistant_message": {"text": "second"}},
            ]
        }
    }
    assert _pick_assistant_text(payload) == "second"


def test_respects_cursor_turn_id():
    """If the user rewound, only visible turns count."""
    payload = {
        "session_data": {
            "cursor_turn_id": "t1",
            "turns": [
                {"id": "t1", "assistant_message": {"text": "kept"}},
                {"id": "t2", "assistant_message": {"text": "discarded-future"}},
            ],
        }
    }
    assert _pick_assistant_text(payload) == "kept"


def test_skips_pending_turn_without_assistant_text():
    payload = {
        "session_data": {
            "turns": [
                {"id": "t1", "assistant_message": {"text": "answered"}},
                {"id": "t2", "assistant_message": {}},
            ]
        }
    }
    assert _pick_assistant_text(payload) == "answered"
