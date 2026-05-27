# Dograh Telegram bot

IM-channel container that bridges Telegram chats to the Dograh API.
Opt into the stack with the `telegram` compose profile:

```bash
docker compose --profile telegram up -d telegram-bot
```

## Design

See:

- `docs/internal/merge-cliclaw/` — the merge plan and per-phase status
- `docs/adr/ADR-100..103` — framework, audio bridge, auth, memory storage

## Status

Phase 1 scaffold only — container builds, exposes `/healthz` on `:8080`.
Real handlers, multi-bot loading, voice paths, and the Syntx-style
inline menu land in subsequent phases.

## Run locally (no Dograh stack needed for the healthcheck)

```bash
cd telegram-bot
docker build -t dograh-telegram-bot .
docker run --rm -p 8080:8080 dograh-telegram-bot
curl http://localhost:8080/healthz
# {"status":"ok","service":"telegram-bot"}
```

## Configuration (filled in by later phases)

| Var | Purpose | Phase |
|---|---|---|
| `DOGRAH_API_URL` | Dograh API base URL, default `http://api:8000` | 2 |
| `REDIS_URL` | Redis for `im:channels:reload` pub/sub | 4 |
| `DATABASE_URL` | Postgres for sessions/memory/scheduler | 2 |
| `TELEGRAM_BOT_TOKEN` | Bootstrap token (Phase 4 prefers loading from DB) | 1 |
| `TELEGRAM_ALLOWED_USERS` | Comma-separated Telegram user IDs allowed to use the bot | 5 |
| `GROQ_API_KEY` | Whisper STT for voice notes | 3 |
| `TELEGRAM_BOT_HEALTH_PORT` | Override the healthcheck port (default 8080) | 1 |
