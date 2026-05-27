# PHASE 1 — Scaffold telegram-bot/ + compose service

**Branch:** `feat/merge-cliclaw-phase-1`

## Goal
Empty-but-working skeleton: container builds, compose service starts on the `telegram` profile, no business logic yet.

## Files to create
```
telegram-bot/
├── Dockerfile             # python:3.12-slim, ffmpeg/libopus apt deps
├── requirements.txt       # aiogram>=3.28, httpx, asyncpg, redis, apscheduler, groq, python-dotenv
├── bot/
│   ├── __init__.py
│   └── main.py            # stub: starts dispatcher, exposes /healthz on :8080
└── README.md
```

## Compose service (in `docker-compose.yaml`)
```yaml
  telegram-bot:
    image: ${REGISTRY:-dograhai}/dograh-telegram-bot:latest
    build: ./telegram-bot
    profiles: ["telegram"]
    depends_on:
      api: { condition: service_healthy }
      redis: { condition: service_healthy }
    environment:
      DOGRAH_API_URL: http://api:8000
      REDIS_URL: ${REDIS_URL:-redis://:redissecret@redis:6379}
      DATABASE_URL: ${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@postgres:5432/postgres}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:-}      # placeholder; Phase 4 loads from DB
      TELEGRAM_ALLOWED_USERS: ${TELEGRAM_ALLOWED_USERS:-}
      GROQ_API_KEY: ${GROQ_API_KEY:-}
    networks: [app-network]
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8080/healthz", "||", "exit", "1"]
      interval: 30s
      start_period: 20s
```

## .env.example additions
```
# Telegram bot (opt-in profile)
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USERS=
GROQ_API_KEY=
```

## Verifier
- `docker compose --profile telegram config` valida senza errori.
- `docker compose --profile telegram build telegram-bot` OK.
- `docker compose --profile telegram up -d telegram-bot` → container healthy in <30s.
- `curl http://localhost:8080/healthz` returns `{"status":"ok"}`.
