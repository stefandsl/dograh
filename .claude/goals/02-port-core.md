# PHASE 2 — Port CliClaw core, wire Dograh API

**Branch:** `feat/merge-cliclaw-phase-2`

## Goal
The bot becomes functional against Dograh: it can list workflows, start a run, send a text message into it, and receive replies. All CLI-backend code is gone.

## Files
- `telegram-bot/bot/dograh_client.py` — async httpx client wrapping the endpoints from `docs/internal/merge-cliclaw/dograh-api-map.md`. Methods at minimum:
  - `list_workflows(...)` → `GET /workflow/summary`
  - `create_run(workflow_id, initial_context)` → `POST /workflow/{id}/runs`
  - `get_run(workflow_id, run_id)` → `GET /workflow/{id}/runs/{run_id}`
  - `health()` → `GET /health`
  - Auth: `X-API-Key` header read from env at boot (Phase 4 makes it per-bot).
- Port files marked KEEP-ADAPT in `docs/internal/merge-cliclaw/cliclaw-import-map.md`:
  - `bot/main.py` (handlers — Router-based per ADR-100)
  - `bot/voice.py` (Groq Whisper STT only)
  - `bot/memory/search.py` + `hooks.py` (rewrite to Postgres FTS per ADR-103)
  - `bot/scheduler.py` (jobs in Postgres `telegram_scheduled_tasks`)
  - `bot/config.py` (stripped to env loading)
- New Alembic migration `api/alembic/versions/<id>_telegram_tables.py` per ADR-103, plus `telegram_scheduled_tasks` for the scheduler.

## Drop
Everything marked DROP in the import map. No `subprocess` calls to `claude-code`, `gemini`, etc.

## Verifier
- `pytest telegram-bot/tests/` ≥ 80% coverage on `dograh_client` (httpx mocked) and `memory` (asyncpg testcontainer).
- Manual: in dev compose, `/workflows` button lists real workflows; `/start <wfid>` creates a run; sending a text message gets a reply.
- `docker compose --profile telegram up -d telegram-bot api` → bot starts cleanly, no SQLite files anywhere in the container.
