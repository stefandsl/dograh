# PHASE 5 — Syntx-style inline menu (9 buttons)

**Branch:** `feat/merge-cliclaw-phase-5`

## Goal
`/start` and `/menu` open a 9-button inline keyboard, every button wired to real functionality. No "Coming soon" inside the bot itself.

## Layout

```
🎙️ Voice Call          (Phase 3 Path 2 — WebApp link)
🤖 Workflows           (list, select active)
💬 Chat with Agent     (text dialogue with active workflow, streaming events)
📋 My Sessions         (list, resume, close)
🧠 Memory              (vault: list / search / add facts)
⏰ Scheduled Tasks     (CRUD)
🖼️ Image Analysis      (upload photo, vision via "image-qa" workflow)
⚙️ Settings            (voice on/off, language)
📊 Status              (/status equivalent — health + active session)
```

## Implementation

`telegram-bot/bot/menu.py` — `build_main_menu()` returns `InlineKeyboardMarkup`.

`telegram-bot/bot/handlers/`:
- `menu.py` — `/start`, `/menu`, callback router for all 9 buttons
- `workflows.py` — `list_workflows`, `select_active`
- `chat.py` — chat-with-agent loop (stream Dograh run events)
- `sessions.py` — `list / resume / close`
- `memory.py` — `list / search / add` (uses `bot/memory/search.py` from Phase 2)
- `scheduler.py` — `list / create / cancel`
- `images.py` — photo upload → workflow run with `image_url` in initial_context
- `settings.py` — per-chat preferences (Postgres)
- `status.py` — health + active session summary

## Edge cases
- No active workflow selected → most buttons short-circuit with "Pick a workflow first" + jump to Workflows.
- Workflow referenced by name doesn't exist (e.g. "image-qa") → reply "Workflow not configured in Dograh — go to <UI link> to set it up." NOT a silent fail.

## Verifier
- `tests/integration/test_menu_flows.py` — aiogram test mode, simulate each button, assert correct handler dispatched and response shape.
- Manual: every button must produce a real action or a clear "do this first" guidance.
