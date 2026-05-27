# PHASE 3 — Voice paths

**Branch:** `feat/merge-cliclaw-phase-3`

## Goal
Two complementary voice paths, both wired per ADR-101.

## Path 1 — Voice-note round-trip (async, always available)

User sends a voice note → bot:
1. Downloads via `getFile`.
2. Groq Whisper STT → text.
3. Posts the text into the user's active workflow run (Dograh API).
4. Pipeline produces a reply (text + audio frames).
5. Bot collects the audio frames, encodes to OGG/Opus, `sendVoice`.

Implementation: `telegram-bot/bot/voice.py` (KEEP-ADAPT) + new
`bot/handlers/voice_notes.py`.

## Path 2 — WebApp link (true real-time WebRTC)

When the user taps **🎙️ Voice Call** in the menu, bot:
1. Calls a new Dograh API endpoint `POST /api/v1/telegram/web-call-link` with `{workflow_id, telegram_chat_id}`.
2. Endpoint creates a workflow run, mints a Fernet-signed session token (5-min TTL, `OSS_JWT_SECRET` as master key), returns `{ url: "https://<host>/embed/<token>" }`.
3. Bot replies with an inline `WebApp` button pointing at that URL.
4. User taps → Telegram opens the embed page → WebRTC client → live agent.

New endpoint lives in `api/routes/telegram.py` (Phase 4 will move it next to the IM channels router).

## Files
- `bot/handlers/voice_notes.py` — Path 1
- `bot/handlers/menu.py` — Path 2 button + handler (also in Phase 5)
- `api/routes/telegram.py` (or merge into Phase 4's `im_channels.py`)
- `api/services/im/web_call_link.py` — Fernet sign/verify

## Verifier
- `tests/integration/test_voice_note_roundtrip.py` — sample voice note in → text+voice reply out, assert audio length > 0.
- `tests/unit/test_web_call_link.py` — round-trip sign/verify, TTL boundary, tamper detection.
- Manual: tap **🎙️ Voice Call**, link opens, can talk to agent in real time.
