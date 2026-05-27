# PHASE 4 — UI IM Channels + backend + multi-bot loader

**Branch:** `feat/merge-cliclaw-phase-4`

## Goal
Admin adds/removes Telegram bot tokens from the Dograh UI; the bot container hot-reloads.

## Backend (FastAPI)

Router: `api/routes/im_channels.py`
- `GET    /api/v1/im/channels` — list (filterable by type, enabled)
- `POST   /api/v1/im/channels/telegram` — create (BOT_TOKEN, allowed_user_ids)
- `PATCH  /api/v1/im/channels/telegram/{id}` — update (enabled, allowed_users)
- `POST   /api/v1/im/channels/telegram/{id}/test` — calls Telegram `getMe`, returns bot username on success
- `DELETE /api/v1/im/channels/telegram/{id}` — delete
- `POST   /api/v1/im/channels/telegram/{id}/rotate-api-key` — mint new Dograh service key, publish reload
- `GET    /api/v1/im/channels/secret-bundle` — internal-only (claim `im:channels:read-secrets`); bot calls at boot

Model: `api/db/models.py` → `ImChannel(id, type, org_id, config_json_encrypted, enabled, created_at, updated_at)`
- Encryption: Fernet with master key derived from `OSS_JWT_SECRET` (no new env var)
- Alembic migration in `api/alembic/versions/<id>_im_channels.py`

Service: `api/services/im/channel_service.py` — auto-mint API key tied to channel; encrypt/decrypt; publish Redis `im:channels:reload`.

## Frontend (Next.js, ui/)

- Sidebar entry "IM Channels" (mirror the Telephony Providers item)
- `src/app/channels/im/page.tsx` — tabs: Telegram (default), WhatsApp (greyed Coming soon), Discord (greyed)
- `<TelegramChannelCard />` — form fields: bot token (secret input), allowed user IDs (chips), enabled toggle, "Test Connection" button, save

## Bot side (`telegram-bot/`)

- At boot, fetch `GET /api/v1/im/channels?type=telegram&enabled=true` via the secret-bundle internal endpoint → load `(bot_token, api_key)` pairs.
- For each pair: create a `Bot` + `Dispatcher`, attach the shared Router tree, start polling.
- Redis pub/sub on `im:channels:reload`: diff loaded vs current, stop removed bots, start new ones, reconfigure changed allowlists.

## Verifier
- `pytest api/tests/test_im_channels.py` — CRUD, encryption round-trip, reload publish.
- `playwright` UI test (or equivalent): add fake token → "Test" returns red error; add real test token (env `TG_TEST_BOT_TOKEN`) → "Test" returns green with bot username.
- Manual: toggle Enabled off → bot stops responding within 5s; toggle on → resumes.
