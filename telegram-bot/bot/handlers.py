"""Phase 5 — Syntx-style menu handlers.

Each menu button has a callback handler here. Heavy use of the
Dograh API client + the existing memory/sessions modules. Text dialogue
runs through Dograh's text-chat session endpoints (see
``api/routes/workflow_text_chat.py``).

Note: the bot is still org-agnostic at the wire level — it sends an
``X-API-Key`` bound to one org's service account (ADR-102), so all
DB lookups in this module use that single org. The chat_id is the
multi-tenancy key on the bot side (one row per chat in
``telegram_sessions`` / ``telegram_memory_facts``).

The org id we use for memory/sessions rows is read from
``MESSAGENET_FALLBACK_ORG_ID`` (deliberately a low-effort env knob for
Phase 5 — Phase 4's IM channels system carries the real org id, and a
follow-up can plumb it through). Defaulting to ``1`` keeps single-org
deployments working out of the box.
"""

from __future__ import annotations

import os
from typing import Any

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from loguru import logger  # noqa: F401  (used by handlers added below)

from . import memory, sessions
from .config import BotConfig
from .dograh_client import DograhClient, DograhClientError
from .formatting import md_to_telegram_html
from .menu import (
    CB_CHAT,
    CB_IMAGES,
    CB_MEMORY,
    CB_SCHED,
    CB_SESSIONS,
    CB_SETTINGS,
    CB_STATUS,
    CB_VOICE,
    CB_WORKFLOWS,
    build_main_menu,
)


# --- FSM ------------------------------------------------------------------
class ChatStates(StatesGroup):
    """Set on the chat when the user toggles `Chat with Agent` mode."""

    chatting = State()


class MemoryStates(StatesGroup):
    awaiting_fact = State()


# --- helpers --------------------------------------------------------------
def _org_id() -> int:
    """Org id used to scope per-chat memory/sessions rows.

    See module docstring — a single bot token belongs to one org via the
    IM channel; pulling that into the handler context cleanly is a
    Phase 4-followup, so for now use an env-level default.
    """
    return int(os.getenv("MESSAGENET_FALLBACK_ORG_ID", "1"))


def _pick_assistant_text(session_payload: dict[str, Any]) -> str:
    """Extract the last assistant message from a text-chat session response.

    Defensive — the session_data shape can be missing turns or have a
    pending turn; we return the most recent visible assistant text, or
    a helpful placeholder if there isn't one yet.
    """
    sd = session_payload.get("session_data") or {}
    turns = sd.get("turns") or []
    cursor = sd.get("cursor_turn_id")
    if cursor is not None:
        # Trim to visible branch.
        out: list[dict[str, Any]] = []
        for t in turns:
            out.append(t)
            if t.get("id") == cursor:
                break
        turns = out
    for t in reversed(turns):
        msg = t.get("assistant_message") or {}
        text = msg.get("text") if isinstance(msg, dict) else None
        if text:
            return str(text)
    return "_(no assistant reply yet — the workflow may be processing)_"


# --- router ---------------------------------------------------------------
def build_menu_router() -> Router:
    r = Router(name="dograh-menu")

    @r.message(Command("menu"))
    async def on_menu_command(message: Message) -> None:
        await message.answer(
            "<b>Menu</b> — pick an action:",
            reply_markup=build_main_menu(),
        )

    # --- callbacks --------------------------------------------------------
    @r.callback_query(lambda c: c.data == CB_VOICE)
    async def cb_voice(
        cq: CallbackQuery, state: FSMContext, dograh: DograhClient
    ) -> None:
        await cq.answer()
        active = await sessions.get_or_create(
            organization_id=_org_id(), chat_id=cq.message.chat.id
        )
        wid = active.get("workflow_id")
        if not wid:
            await cq.message.answer(
                "🎙️ Pick a workflow first via <b>🤖 Workflows</b>."
            )
            return
        try:
            link = await dograh.request_web_call_link(
                workflow_id=int(wid), telegram_chat_id=cq.message.chat.id
            )
        except DograhClientError as exc:
            await cq.message.answer(f"❌ Dograh API error: {exc}")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🎙️ Open Voice Call",
                web_app=WebAppInfo(url=link["url"]),
            )
        ]])
        await cq.message.answer(
            f"Tap to start a voice call (link valid {link['expires_in_seconds']}s):",
            reply_markup=kb,
        )

    @r.callback_query(lambda c: c.data == CB_WORKFLOWS)
    async def cb_workflows(cq: CallbackQuery, dograh: DograhClient) -> None:
        await cq.answer()
        try:
            workflows = await dograh.list_workflows_summary()
        except DograhClientError as exc:
            await cq.message.answer(f"❌ Dograh API error: {exc}")
            return
        if not workflows:
            await cq.message.answer(
                "No workflows yet. Create one in the Dograh UI first."
            )
            return
        # Inline keyboard: one button per workflow that sets it as active.
        rows: list[list[InlineKeyboardButton]] = []
        for w in workflows[:20]:
            wid = w.get("id") or w.get("workflow_id")
            name = (w.get("name") or "(untitled)")[:40]
            if wid is None:
                continue
            rows.append([
                InlineKeyboardButton(
                    text=f"▶ {name} (id {wid})",
                    callback_data=f"wf:pick:{wid}",
                )
            ])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await cq.message.answer(
            "<b>Workflows</b> — tap to set as active:", reply_markup=kb
        )

    @r.callback_query(lambda c: (c.data or "").startswith("wf:pick:"))
    async def cb_pick_workflow(cq: CallbackQuery) -> None:
        await cq.answer()
        try:
            wid = int((cq.data or "").rsplit(":", 1)[1])
        except (ValueError, IndexError):
            await cq.message.answer("Bad workflow id in callback")
            return
        await sessions.get_or_create(
            organization_id=_org_id(), chat_id=cq.message.chat.id
        )
        await sessions.set_active_workflow(
            organization_id=_org_id(),
            chat_id=cq.message.chat.id,
            workflow_id=wid,
        )
        await cq.message.answer(
            f"✅ Active workflow set to <code>{wid}</code>. "
            "Tap <b>💬 Chat with Agent</b> or send a text message to start."
        )

    @r.callback_query(lambda c: c.data == CB_CHAT)
    async def cb_chat(
        cq: CallbackQuery, state: FSMContext, dograh: DograhClient
    ) -> None:
        await cq.answer()
        active = await sessions.get_or_create(
            organization_id=_org_id(), chat_id=cq.message.chat.id
        )
        wid = active.get("workflow_id")
        if not wid:
            await cq.message.answer(
                "Pick a workflow first via <b>🤖 Workflows</b>."
            )
            return
        # Create a text-chat session if we don't have one yet.
        if not active.get("workflow_run_id"):
            try:
                resp = await dograh.create_text_chat_session(int(wid))
            except DograhClientError as exc:
                await cq.message.answer(f"❌ Dograh API error: {exc}")
                return
            run_id = int(resp.get("workflow_run_id", 0))
            await sessions.set_active_run(
                organization_id=_org_id(),
                chat_id=cq.message.chat.id,
                workflow_run_id=run_id,
            )
        await state.set_state(ChatStates.chatting)
        await cq.message.answer(
            "💬 Chat mode <b>on</b>. Send a message to talk to the agent. "
            "Use /endchat to exit."
        )

    @r.message(Command("endchat"))
    async def on_endchat(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Chat mode <b>off</b>.")

    # Main text handler — only routes when chat mode is on. Other text
    # messages fall through to the placeholder in bot/main.py.
    @r.message(ChatStates.chatting)
    async def on_chat_message(
        message: Message, dograh: DograhClient
    ) -> None:
        if not message.text:
            return
        active = await sessions.get_or_create(
            organization_id=_org_id(), chat_id=message.chat.id
        )
        wid = active.get("workflow_id")
        run_id = active.get("workflow_run_id")
        if not wid or not run_id:
            await message.answer(
                "Lost the active session — re-open with <b>💬 Chat with Agent</b>."
            )
            return
        try:
            resp = await dograh.append_text_chat_message(
                workflow_id=int(wid),
                run_id=int(run_id),
                text=message.text,
            )
        except DograhClientError as exc:
            await message.answer(f"❌ Dograh API error: {exc}")
            return
        reply = _pick_assistant_text(resp)
        await message.answer(md_to_telegram_html(reply))

    @r.callback_query(lambda c: c.data == CB_SESSIONS)
    async def cb_sessions(cq: CallbackQuery) -> None:
        await cq.answer()
        s = await sessions.get_or_create(
            organization_id=_org_id(), chat_id=cq.message.chat.id
        )
        lines = ["<b>Current session</b>"]
        lines.append(f"workflow_id: <code>{s.get('workflow_id') or '—'}</code>")
        lines.append(f"workflow_run_id: <code>{s.get('workflow_run_id') or '—'}</code>")
        lines.append(f"state: <code>{s.get('state') or 'idle'}</code>")
        await cq.message.answer("\n".join(lines))

    @r.callback_query(lambda c: c.data == CB_MEMORY)
    async def cb_memory(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        facts = await memory.search_facts(
            organization_id=_org_id(),
            chat_id=cq.message.chat.id,
            query="",
            limit=10,
        )
        if not facts:
            await cq.message.answer(
                "🧠 No facts yet. Use <code>/remember &lt;text&gt;</code> "
                "to add one, or <code>/memory &lt;query&gt;</code> to search."
            )
            return
        lines = ["<b>🧠 Recent facts</b>"]
        for f in facts:
            ts = f["created_at"].strftime("%Y-%m-%d") if f.get("created_at") else "?"
            lines.append(f"• <code>{f['id']}</code> [{ts}] {f['body'][:120]}")
        await cq.message.answer("\n".join(lines))

    @r.message(Command("remember"))
    async def on_remember(message: Message) -> None:
        text = (message.text or "").removeprefix("/remember").strip()
        if not text:
            await message.answer("Usage: <code>/remember &lt;fact&gt;</code>")
            return
        fid = await memory.add_fact(
            organization_id=_org_id(),
            chat_id=message.chat.id,
            body=text,
        )
        await message.answer(f"✅ Saved as fact <code>{fid}</code>.")

    @r.message(Command("memory"))
    async def on_memory_search(message: Message) -> None:
        query = (message.text or "").removeprefix("/memory").strip()
        facts = await memory.search_facts(
            organization_id=_org_id(),
            chat_id=message.chat.id,
            query=query,
            limit=10,
        )
        if not facts:
            await message.answer(f"No matches for <code>{query}</code>")
            return
        lines = [f"<b>🧠 Results for</b> <code>{query}</code>"]
        for f in facts:
            lines.append(f"• <code>{f['id']}</code> {f['body'][:200]}")
        await message.answer("\n".join(lines))

    @r.callback_query(lambda c: c.data == CB_SCHED)
    async def cb_sched(cq: CallbackQuery) -> None:
        await cq.answer()
        await cq.message.answer(
            "⏰ <b>Scheduled tasks</b>\n\n"
            "CRUD UI lands in a follow-up. The schema is ready "
            "(<code>telegram_scheduled_tasks</code> table); the runner "
            "will use it once we wire APScheduler on the bot side."
        )

    @r.callback_query(lambda c: c.data == CB_IMAGES)
    async def cb_images(cq: CallbackQuery, dograh: DograhClient) -> None:
        await cq.answer()
        # Look for a workflow named "image-qa" (case-insensitive). If
        # absent, give the user a clear next step rather than failing.
        try:
            workflows = await dograh.list_workflows_summary()
        except DograhClientError as exc:
            await cq.message.answer(f"❌ Dograh API error: {exc}")
            return
        match = next(
            (w for w in workflows if (w.get("name") or "").lower() == "image-qa"),
            None,
        )
        if not match:
            await cq.message.answer(
                "🖼️ <b>Image Analysis</b>\n\n"
                "No workflow named <code>image-qa</code> found. "
                "Create one in the Dograh UI (a vision-LLM workflow that "
                "reads <code>image_url</code> from initial_context) and "
                "I'll route photos here automatically."
            )
            return
        await cq.message.answer(
            "🖼️ Send a photo. I'll upload it to the <code>image-qa</code> "
            "workflow and reply with what the agent says.\n"
            "(Photo upload wiring lands in a follow-up.)"
        )

    @r.callback_query(lambda c: c.data == CB_SETTINGS)
    async def cb_settings(cq: CallbackQuery) -> None:
        await cq.answer()
        await cq.message.answer(
            "⚙️ <b>Settings</b>\n\n"
            "Per-chat settings (voice on/off, language) land in a follow-up. "
            "For now: env-level config only "
            "(see <code>TELEGRAM_ALLOWED_USERS</code>, <code>GROQ_API_KEY</code>)."
        )

    @r.callback_query(lambda c: c.data == CB_STATUS)
    async def cb_status(cq: CallbackQuery, dograh: DograhClient, cfg: BotConfig) -> None:
        await cq.answer()
        try:
            api_health = await dograh.health()
            api_status = api_health.get("status", "?")
        except DograhClientError as exc:
            api_status = f"error ({exc.status})"
        s = await sessions.get_or_create(
            organization_id=_org_id(), chat_id=cq.message.chat.id
        )
        lines = [
            "<b>📊 Status</b>",
            f"Dograh API: <code>{api_status}</code>",
            f"Active workflow: <code>{s.get('workflow_id') or '—'}</code>",
            f"Active run: <code>{s.get('workflow_run_id') or '—'}</code>",
            f"Voice STT: <code>"
            + ("configured" if cfg.groq_api_key else "off (set GROQ_API_KEY)")
            + "</code>",
        ]
        await cq.message.answer("\n".join(lines))

    # Image messages — route to image-qa workflow if registered.
    @r.message(lambda m: m.photo is not None and len(m.photo or []) > 0)
    async def on_photo(
        message: Message, bot: Bot, dograh: DograhClient
    ) -> None:
        await message.answer(
            "🖼️ Photo received. The image-analysis path is the next "
            "follow-up — for now, use the <b>🖼️ Image Analysis</b> "
            "button to check setup."
        )
        logger.info(
            f"[handlers] photo from chat={message.chat.id} "
            f"file_id={message.photo[-1].file_id}"
        )

    return r
