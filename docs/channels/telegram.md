---
title: "Telegram IM Channel"
description: "Run a Telegram bot frontend on your Bellerophone deployment."
---

## Overview

The Telegram channel turns Bellerophone into a Telegram bot. Once enabled,
users can:

- 🎙️ Open a real-time voice call to one of your workflows (via a
  signed WebApp button → in-browser WebRTC client)
- 💬 Chat with an agent in plain text (turn-based, backed by Bellerophone's
  text-chat session API)
- 🧠 Save and search facts ("memory vault")
- 🤖 Pick which workflow handles their chat
- Send voice notes that get transcribed (Groq Whisper) and routed into
  the workflow

Everything is managed from the Bellerophone UI at `/channels/im`. The bot
itself is an opt-in container (`docker compose --profile telegram up`).

## Architecture

```
┌────────────┐         ┌──────────────┐         ┌──────────────┐
│  Telegram  │ ◄────► │ telegram-bot │ ◄────► │  Bellerophone api  │
│   Bot API  │   long │  container   │   HTTP  │  (FastAPI)   │
└────────────┘  poll  │  (aiogram)   │         └──────┬───────┘
                      └──────┬───────┘                │
                             │ Redis pub/sub          │
                             │ im:channels:reload     │
                             └────────────────────────┘
                                                      │
                              Real-time voice path    │
                              (WebApp button → 302)   ▼
                                              ┌──────────────┐
                                              │  WebRTC      │
                                              │  embed page  │
                                              │  + coturn    │
                                              └──────────────┘
```

- One container, many bots. The bot fetches every enabled Telegram
  channel from `/api/v1/im/channels/secret-bundle` at boot and spins
  up one `aiogram.Dispatcher` per bot token, all sharing the same
  Router tree.
- Hot reload. When an admin enables/disables/edits a channel in the
  UI, the api publishes on Redis `im:channels:reload`; the bot diffs
  the new bundle against what's running and starts/stops/restarts
  dispatchers without a process restart.
- Auth. Each IM channel owns a service-account API key in the same
  org (auto-minted at creation); the bot uses that key as `X-API-Key`
  on every Bellerophone API call.

See `docs/channels/architecture.md` for the mermaid version and
`docs/adr/ADR-100..103` for the decisions that shaped this layout.

## Prerequisites

- A Bellerophone instance running (`docker compose up -d`).
- A Telegram bot token from [@BotFather](https://t.me/BotFather) — `/newbot`,
  follow the prompts, copy the token.
- *(Optional)* A Groq API key for voice-note STT. Without it, the bot
  acknowledges voice notes but doesn't transcribe.

## Step 1 — Enable the Telegram profile

Set the shared internal secret (the api and bot containers both read it):

```bash
# in your .env
IM_INTERNAL_SECRET=$(openssl rand -hex 32)
# optional, only if you want voice-note STT
GROQ_API_KEY=gsk_...
```

Then bring up the bot container:

```bash
docker compose --profile telegram up -d telegram-bot
```

You should see in `docker logs dograh-telegram-bot`:

```
[telegram-bot] health server listening on :8080
[telegram-bot] multi-channel mode online
[channels] reload done — 0 bot(s) running
```

`0 bots` is expected — you haven't registered any tokens yet.

## Step 2 — Register the bot in the Bellerophone UI

Open the Bellerophone UI → sidebar → **IM Channels**. Click **+ Add Telegram bot**.

Fill in:

- **Name** — any label, e.g. `ops-bot`
- **Bot token** — the @BotFather token (`123456789:ABC…`)
- **Allowed Telegram user IDs** — comma-separated. Get your own ID by
  messaging [@userinfobot](https://t.me/userinfobot). Leave empty to
  allow anyone who messages the bot.
- **Enabled** — on by default

Click **Save**. The toast surfaces a one-time API key — you don't need
to copy it (the bot reads it via the secret-bundle endpoint), but you
can if you want to make Bellerophone API calls as that service account.

Within ~1 second of clicking Save:

- the api publishes on Redis `im:channels:reload`
- the bot pulls the new bundle and starts polling
- the bot's logs show `[channels] started channel N (ops-bot) as @your_bot_username`

## Step 3 — Talk to the bot

Open Telegram, search for your bot (`@your_bot_username`), and send `/start`.
You'll see the 9-button menu:

```
🎙️ Voice Call          🤖 Workflows
💬 Chat with Agent     📋 My Sessions
🧠 Memory              ⏰ Scheduled Tasks
🖼️ Image Analysis      ⚙️ Settings
📊 Status
```

Typical first-run flow:

1. Tap **🤖 Workflows**, pick the workflow you want this chat to route into.
2. Tap **💬 Chat with Agent** to start a text-chat session.
3. Send messages — replies come from the workflow's pipeline. `/endchat`
   to exit chat mode.
4. Tap **🎙️ Voice Call** for real-time WebRTC (opens a WebApp link
   signed with a 5-minute TTL).
5. Send a voice note while in chat mode → Groq Whisper STTs and your
   text goes into the workflow.

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| Bot doesn't respond to `/start` | Token isn't loaded yet | Check the bot logs: `docker logs dograh-telegram-bot \| grep channels`. The first line of a healthy boot is `[channels] reload done — N bot(s) running`. If N=0, re-save the channel in the UI; if the api is unreachable, fix that first. |
| `/api/v1/im/channels/secret-bundle` 401 | `IM_INTERNAL_SECRET` mismatch between api and bot containers | Both must read the same value. Set it in `.env` and `docker compose up -d --force-recreate api telegram-bot`. |
| `/api/v1/im/channels/secret-bundle` 503 | `IM_INTERNAL_SECRET` not set on the api container | Set it. |
| Workflows list is empty | No workflows in the org behind the channel's API key | Create one in the UI; the bot will see it on next call. |
| Voice note arrives but no transcript | `GROQ_API_KEY` not set in the bot container | Set it in `.env`, `docker compose up -d --force-recreate telegram-bot`. |
| Voice call link returns 404 in the browser | Token expired (default TTL 5 min) | Tap the button again to mint a fresh one. Override via `TELEGRAM_WEBCALL_TTL_SECONDS` on the api container if you want longer windows. |
| `/im/channels` UI page is blank | Generated SDK doesn't yet have the new routes | This is expected on first deploy. Run `npm run generate-client` in `ui/` against an api with the routes and replace the hand-rolled fetch helpers in `ui/src/lib/imChannels.ts`. Or just use the page as-is — it works either way. |

## Environment reference

Bot container (`telegram-bot` service):

| Var | Purpose |
|---|---|
| `IM_INTERNAL_SECRET` | Shared secret with the api for the `/secret-bundle` endpoint. Enables multi-channel mode. |
| `DOGRAH_API_URL` | Defaults to `http://api:8000` (docker network). |
| `REDIS_URL` | For the `im:channels:reload` subscription. |
| `DATABASE_URL` | Bot uses Postgres for memory + sessions + scheduled tasks. |
| `GROQ_API_KEY` | Voice-note STT (Whisper). Optional. |
| `TELEGRAM_BOT_TOKEN` | Bootstrap mode only — when `IM_INTERNAL_SECRET` is unset, the bot runs a single dispatcher from this token. |
| `TELEGRAM_ALLOWED_USERS` | Bootstrap-mode allowlist (CSV). Multi-channel mode reads the allowlist from each channel row. |
| `MESSAGENET_FALLBACK_ORG_ID` | Phase-5 placeholder for the org used by memory/sessions DB rows (default `1`). Per-channel org plumbing is a follow-up. |

API container (`api` service):

| Var | Purpose |
|---|---|
| `IM_INTERNAL_SECRET` | Same value the bot reads — without it, `/secret-bundle` returns 503. |
| `TELEGRAM_WEBCALL_TTL_SECONDS` | Override the WebApp-link TTL (default 300). |
| `OSS_JWT_SECRET` | Used to derive the Fernet key that encrypts both channel configs and web-call link tokens. |
