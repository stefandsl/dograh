"""Syntx-style inline menu — the 9-button keyboard that `/start`
and `/menu` open.

Each button maps to a callback_data string that the dispatcher in
``handlers.py`` routes. Voice Call is rendered as a regular callback;
the handler then emits a WebApp button per-chat (since WebApp URLs are
per-call, signed and short-lived per ADR-101).
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# Stable callback prefixes — keep in sync with handlers.py dispatcher.
CB_VOICE = "menu:voice"
CB_WORKFLOWS = "menu:workflows"
CB_CHAT = "menu:chat"
CB_SESSIONS = "menu:sessions"
CB_MEMORY = "menu:memory"
CB_SCHED = "menu:sched"
CB_IMAGES = "menu:images"
CB_SETTINGS = "menu:settings"
CB_STATUS = "menu:status"


def build_main_menu() -> InlineKeyboardMarkup:
    """The 9-button inline keyboard rendered by ``/start`` and ``/menu``.

    Layout: two columns by default — Telegram clients render two-wide
    inline rows comfortably, and three columns is too crowded on phones.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎙️ Voice Call", callback_data=CB_VOICE),
                InlineKeyboardButton(text="🤖 Workflows", callback_data=CB_WORKFLOWS),
            ],
            [
                InlineKeyboardButton(text="💬 Chat with Agent", callback_data=CB_CHAT),
                InlineKeyboardButton(text="📋 My Sessions", callback_data=CB_SESSIONS),
            ],
            [
                InlineKeyboardButton(text="🧠 Memory", callback_data=CB_MEMORY),
                InlineKeyboardButton(text="⏰ Scheduled Tasks", callback_data=CB_SCHED),
            ],
            [
                InlineKeyboardButton(text="🖼️ Image Analysis", callback_data=CB_IMAGES),
                InlineKeyboardButton(text="⚙️ Settings", callback_data=CB_SETTINGS),
            ],
            [
                InlineKeyboardButton(text="📊 Status", callback_data=CB_STATUS),
            ],
        ]
    )
