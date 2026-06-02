# Phase 0 — Research summary (CliClaw → Bellerophone merge)

This is the synthesis of the Phase 0 read-only research. Two map docs
and four ADRs cover the substance; this file is the human-readable
index.

## Outputs

- **API map** → [`dograh-api-map.md`](./dograh-api-map.md) — every
  Bellerophone endpoint the bot can call, with the auth model the bot uses.
- **Import map** → [`cliclaw-import-map.md`](./cliclaw-import-map.md) —
  which CliClaw files survive (KEEP-AS-IS / KEEP-ADAPT / DROP).
- **ADR-100** — Telegram framework (`aiogram 3.28+`)
- **ADR-101** — Audio bridge (voice-note round-trip + WebApp link;
  Path A as written in the master plan is not physically possible)
- **ADR-102** — Bot ↔ Bellerophone API auth (`X-API-Key` per IM channel row)
- **ADR-103** — Memory storage (Postgres FTS, drop SQLite/FTS5)

## Key surprises vs the master plan

1. **The Telegram Bot API has no real-time voice.** Bots can only
   exchange voice notes (discrete OGG/Opus files) and observe
   video-chat lifecycle events. A bot cannot join or stream a
   voice chat — that's MTProto/userbot territory. The master plan's
   Path A ("aiortc in the bot") was unimplementable as written.
   ADR-101 documents the actual options.

2. **There's no IM channel abstraction in Bellerophone yet.** Phase 4 is
   greenfield, not "extend existing pattern". The telephony providers
   directory (`api/services/telephony/providers/`) is the template
   we'll mirror.

3. **No dedicated TTS endpoint.** TTS happens inside a workflow run.
   The voice-note "reply" path in Phase 3 will start a workflow run
   per voice message and capture its audio output frames. That's
   slightly more orchestration than the master implied.

4. **`X-API-Key` already exists.** ADR-102 reuses it instead of
   introducing a new `X-Internal-Service-Token` pattern. The
   shared-secret idea from the master plan is unnecessary.

## What's confirmed compatible

- aiogram 3.28+ on Python 3.12 (current container base).
- aiortc in `python:3.12-slim` with apt deps (libopus, libsrtp,
  libvpx, ffmpeg). Not used in this merge per ADR-101, but the option
  is documented for future MTProto userbot work.
- Postgres FTS (`to_tsvector('simple') + GIN`) covers everything
  SQLite FTS5 did for the CliClaw memory vault.

## Out of scope flagged for later

- Per-end-user OAuth ("link my Telegram to my Bellerophone account") — ADR-102
  mentions a future shape.
- Userbot/MTProto path for true real-time voice chat participation —
  ADR-101 flags it.
- WhatsApp + Discord channels — the UI in Phase 4 reserves tabs for
  them as "Coming soon".
