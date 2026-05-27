# PHASE 0 — Research & Mapping

**Branch:** `feat/merge-cliclaw-phase-0`
**Status:** ✅ Done (this commit)

## Goal
No code. Map the integration surface, decide architecture, document with ADRs.

## Outputs
- `docs/internal/merge-cliclaw/dograh-api-map.md` — every endpoint the bot will call
- `docs/internal/merge-cliclaw/cliclaw-import-map.md` — KEEP / KEEP-ADAPT / DROP per file
- `docs/internal/merge-cliclaw/research.md` — index + key surprises
- `docs/adr/ADR-100-telegram-framework.md` — aiogram 3.28+
- `docs/adr/ADR-101-audio-bridge.md` — voice-note round-trip + WebApp link
- `docs/adr/ADR-102-bot-to-api-auth.md` — X-API-Key per IM channel
- `docs/adr/ADR-103-memory-storage.md` — Postgres FTS, drop SQLite

## Verifier
- The 4 ADRs exist.
- The import map exists and lists every Python file under `/tmp/cliclaw/bot/`.
- The API map exists and every cited path matches a real route in `api/routes/` (grep-verified).
