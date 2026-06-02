# ADR-101 — Audio bridge between Telegram and Bellerophone

**Status:** Accepted
**Date:** 2026-05-27
**Context:** Phase 0 of the CliClaw → Bellerophone merge. The MERGE-MASTER plan
asks for a "Voice Call" button that bridges a Telegram conversation to
a Bellerophone Web Call (WebRTC). The plan offered Path A (aiortc in the bot)
and Path B (signed WebApp link) as alternatives.

## Decision

**Use both, but neither is "Path A as described in the master plan".**
The master's Path A — "bot uses aiortc to bridge Telegram voice ↔ Bellerophone
WebRTC in real time" — is not physically possible. Telegram Bot API 10.0
(2026-05-08) exposes **no real-time voice channel for bots**: a bot can
only receive/send discrete `voice` messages (Opus-in-OGG files) and
observe video-chat lifecycle events; it cannot join a voice chat or
stream audio. Real-time voice on Telegram is a userbot (MTProto)
concern, not a Bot API one. aiortc would have no Telegram-side stream
to attach to.

What we ship instead:

1. **Async "voice chat" via voice-note round-trip** (always available).
   User sends a voice note → bot downloads via `getFile` → Groq Whisper
   STT → posts as a text message into the active Bellerophone workflow run →
   pipeline produces a text reply → bot synthesises via the Bellerophone
   pipeline's TTS leg and sends `sendVoice`. Turn-based, ~1-3 s
   round-trip, what every shipping AI voice bot on Telegram does today.
2. **True real-time voice via signed WebApp link** (when the user wants
   full-duplex). The bot generates a Fernet-signed, short-TTL
   (`OSS_JWT_SECRET` as master key, 5-min TTL) URL pointing at a new
   `/api/v1/telegram/web-call-link` endpoint on the Bellerophone API. The
   endpoint resolves the token to `{workflow_id, user_id,
   workflow_run_id}` and 302-redirects into the public embed signaling
   page (`/embed/<session_token>`). User taps the menu button, browser
   opens the WebRTC client, talks to the agent in real time.

## Why not Path A (aiortc + Bot API)

- A bot has no live audio stream from Telegram to feed aiortc.
- The userbot alternative (Pyrogram/Telethon + pytgcalls) is a
  different security model (phone-number registration, not bot token),
  not a fit for a multi-tenant SaaS.
- Even if a workaround existed, the latency of voice-note packaging
  (Opus encode + Telegram CDN round-trip) would dominate the audio
  path and defeat the point of real time.

## Why not Path B alone

The WebApp link is *correct* for true real time but it's friction —
you've broken out of Telegram. The voice-note path is the conversational
default that matches user expectations, and it works with one tap.
Doing both costs almost nothing because they share the same Bellerophone
workflow run.

## Implications

- `requirements.txt` does **not** pin aiortc. (We may add it later if
  the userbot path opens up; not in scope.)
- `Dockerfile` is `python:3.12-slim` with `ffmpeg`, `libopus0`,
  `libopusfile0` apt deps for voice-note transcoding.
- New API endpoint: `POST /api/v1/telegram/web-call-link` (Phase 4 work,
  ADR-102 covers its auth).
- Voice-note round-trip is gated by a per-org TTS budget check —
  re-using Bellerophone's existing quota service.
