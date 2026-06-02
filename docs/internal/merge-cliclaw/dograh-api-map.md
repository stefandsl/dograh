# Bellerophone API endpoint map (for Telegram bot integration)

All endpoints mount under `/api/v1`. Auth is via either:
- **`X-API-Key: <key>`** — preferred for service-to-service (the bot)
- **`Authorization: Bearer <jwt>`** — first-party / browser flow

Source: `api/services/auth/depends.py:19-129` and the route modules
listed below.

## Health

| Method | Path | Auth | Source | Purpose |
|---|---|---|---|---|
| GET | `/health` | none | api/routes/main.py | Liveness + deployment-mode probe (used by bot startup) |

## Workflow CRUD

| Method | Path | Auth | Source | Purpose |
|---|---|---|---|---|
| GET    | `/workflow/fetch` | JWT/KEY | routes/workflow.py | List workflows (filterable by status) |
| GET    | `/workflow/fetch/{workflow_id}` | JWT/KEY | routes/workflow.py | Fetch single workflow (draft preferred) |
| GET    | `/workflow/summary` | JWT/KEY | routes/workflow.py | Minimal list (id + name) — what the bot uses |
| GET    | `/workflow/count` | JWT/KEY | routes/workflow.py | Counts by status |
| POST   | `/workflow/create/definition` | JWT/KEY | routes/workflow.py | Create from node/edge JSON |
| POST   | `/workflow/create/template` | JWT/KEY | routes/workflow.py | AI-generated from template |
| PUT    | `/workflow/{workflow_id}` | JWT/KEY | routes/workflow.py | Update (creates draft) |
| POST   | `/workflow/{workflow_id}/validate` | JWT/KEY | routes/workflow.py | Validate without publishing |
| POST   | `/workflow/{workflow_id}/publish` | JWT/KEY | routes/workflow.py | Publish draft to live |
| POST   | `/workflow/{workflow_id}/create-draft` | JWT/KEY | routes/workflow.py | Create draft from published |
| GET    | `/workflow/{workflow_id}/versions` | JWT/KEY | routes/workflow.py | Version history |
| PUT    | `/workflow/{workflow_id}/status` | JWT/KEY | routes/workflow.py | Archive / unarchive |
| PUT    | `/workflow/{workflow_id}/folder` | JWT/KEY | routes/workflow.py | Move to folder |
| POST   | `/workflow/{workflow_id}/duplicate` | JWT/KEY | routes/workflow.py | Clone |

## Workflow runs

| Method | Path | Auth | Source | Purpose |
|---|---|---|---|---|
| POST | `/workflow/{workflow_id}/runs` | JWT/KEY | routes/workflow.py | Create run (manual mode) — what the bot uses to start a session |
| GET  | `/workflow/{workflow_id}/runs` | JWT/KEY | routes/workflow.py | List (paginated, filterable) |
| GET  | `/workflow/{workflow_id}/runs/{run_id}` | JWT/KEY | routes/workflow.py | Single run incl. transcript/recording URLs + cost |
| GET  | `/workflow/{workflow_id}/report` | JWT/KEY | routes/workflow.py | CSV download |

## WebRTC / Web Call

| Method | Path | Auth | Source | Purpose |
|---|---|---|---|---|
| WS  | `/ws/signaling/{workflow_id}/{workflow_run_id}` | JWT | routes/webrtc_signaling.py | SmallWebRTC signaling — first-party browser flow |
| WS  | `/ws/public/signaling/{session_token}` | session_token | routes/webrtc_signaling.py | Public embed signaling — what the WebApp link uses |
| GET | `/turn-credentials/credentials` | JWT | routes/main.py | HMAC time-limited TURN creds |
| GET | `/public/embed/turn-credentials/{session_token}` | session_token | routes/public_embed.py | Public TURN creds for the embed page |

## Telephony

| Method | Path | Auth | Source | Purpose |
|---|---|---|---|---|
| POST | `/telephony/initiate-call` | JWT | routes/telephony.py | Outbound from browser |
| POST | `/telephony/inbound/run` | provider signature | routes/telephony.py | Inbound webhook dispatcher |
| WS   | `/telephony/ws/{workflow_id}/{user_id}/{workflow_run_id}` | query token | routes/telephony.py | Real-time call WebSocket |
| WS   | `/telephony/ws/ari` | query params | routes/telephony.py | ARI/MessageNet audio leg |

## Public agent (programmatic trigger)

| Method | Path | Auth | Source | Purpose |
|---|---|---|---|---|
| POST | `/public/agent/{uuid}` | X-API-Key | routes/public_agent.py | Trigger published agent |
| POST | `/public/agent/workflow/{workflow_uuid}` | X-API-Key | routes/public_agent.py | Trigger by workflow UUID |
| POST | `/public/agent/test/{uuid}` | X-API-Key | routes/public_agent.py | Test agent run |

Payload: `{ "phone_number": "...", "initial_context": {...}, "telephony_configuration_id": N }`

## User configurations & API keys

| Method | Path | Auth | Source | Purpose |
|---|---|---|---|---|
| GET    | `/user/configurations/user` | JWT | routes/user_configurations.py | User config (LLM/STT/TTS providers) |
| GET/POST/DELETE | `/user/api-keys` | JWT | routes/user_api_keys.py | Create + manage X-API-Key secrets — what auto-mints keys for the IM channels |

## Models + migrations

- **SQLAlchemy models:** `api/db/models.py` (~46 KB, single file)
- **Alembic dir:** `api/alembic/versions/` (~95 migrations, single timeline)
- **Migration scripts:** `./scripts/makemigrate.sh "<desc>"` then `./scripts/migrate.sh`

## What does NOT exist

- **No dedicated TTS endpoint.** TTS happens inside workflow execution
  (configured per-user via `/user/configurations/user`). For the
  voice-note round-trip in Phase 3, the bot generates voice by routing
  the user's text into an active workflow run and capturing the
  audio frame stream.
- **No IM channel abstraction.** Telephony providers (Twilio, Vonage,
  Telnyx, ARI, Plivo, MessageNet, Cloudonix) live under
  `api/services/telephony/providers/`. There is no analogous
  `api/services/im/` — Phase 4 introduces it.
- **No `/api/v1/telegram/web-call-link` endpoint.** Phase 4 adds it
  (referenced by ADR-101).
