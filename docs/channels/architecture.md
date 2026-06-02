---
title: "IM Channels Architecture"
description: "How the Telegram bot, the api, and the WebRTC client fit together."
---

## Component map

```mermaid
flowchart LR
    User[Telegram user]
    BotAPI[Telegram Bot API]
    Container[telegram-bot container<br/>aiogram dispatcher×N]
    API[Bellerophone api<br/>FastAPI]
    Pg[(Postgres)]
    Redis[(Redis)]
    Browser[User's browser<br/>WebApp]
    Embed[Bellerophone WebRTC<br/>embed page]
    Coturn[coturn TURN]
    Pipeline[Workflow pipeline<br/>pipecat STT/LLM/TTS]

    User <-->|/start /menu<br/>text/voice| BotAPI
    BotAPI <-->|long-poll| Container

    Container -->|X-API-Key| API
    Container <-->|GET /secret-bundle<br/>SUB im:channels:reload| API
    Container --- Pg

    API --- Pg
    API --- Redis
    Redis <-->|PUB im:channels:reload| Container

    Container -.->|menu → 🎙️ Voice Call<br/>POST /api/v1/telegram/web-call-link| API
    API -.->|signed URL| Container
    Container -->|WebApp button| User
    User -->|tap| Browser
    Browser -->|loads| Embed
    Embed <-->|WebRTC + TURN| Coturn
    Embed <-->|pipeline events| Pipeline
    Pipeline --- API
```

## Outbound text-chat sequence

```mermaid
sequenceDiagram
    actor U as Telegram user
    participant TG as Telegram Bot API
    participant B as telegram-bot
    participant A as Bellerophone api

    U->>TG: /menu
    TG->>B: update
    B-->>TG: 9-button keyboard
    TG-->>U: shows menu

    U->>TG: tap "💬 Chat with Agent"
    TG->>B: callback_query
    B->>A: POST /api/v1/workflow/{wf}/text-chat/sessions
    A-->>B: { workflow_run_id, session_data, ... }
    Note over B: persist workflow_run_id in telegram_sessions
    B-->>TG: "Chat mode on"

    U->>TG: "Ciao"
    TG->>B: message
    B->>A: POST /workflow/{wf}/text-chat/sessions/{run}/messages
    A-->>B: { session_data.turns[-1].assistant_message.text }
    B-->>TG: assistant reply (HTML-formatted)
    TG-->>U: reply
```

## Voice-call sequence (real-time, WebApp link path)

```mermaid
sequenceDiagram
    actor U as Telegram user
    participant TG as Telegram Bot API
    participant B as telegram-bot
    participant A as Bellerophone api
    participant Br as Browser (WebApp)
    participant Co as coturn / WebRTC

    U->>TG: tap "🎙️ Voice Call"
    TG->>B: callback_query
    B->>A: POST /api/v1/telegram/web-call-link {workflow_id, chat_id}
    Note over A: create SmallWebRTC workflow_run<br/>Fernet-sign token (5 min TTL)
    A-->>B: { url: https://host/api/v1/telegram/web-call/<token> }
    B-->>TG: WebApp button
    U->>TG: tap WebApp button
    TG->>Br: open URL
    Br->>A: GET /telegram/web-call/<token>
    A-->>Br: embed page bootstrap
    Br<-->Co: WebRTC + TURN
    Br<-->A: pipeline events (STT/LLM/TTS)
```

## Hot-reload of bot tokens

```mermaid
sequenceDiagram
    actor Admin
    participant UI as Bellerophone UI
    participant A as Bellerophone api
    participant R as Redis
    participant B as telegram-bot

    Admin->>UI: enable/edit/disable channel
    UI->>A: PATCH /api/v1/im/channels/telegram/{id}
    A->>A: Fernet-encrypt config, write row
    A->>R: PUBLISH im:channels:reload "1"
    R-->>B: message
    B->>A: GET /api/v1/im/channels/secret-bundle<br/>(X-IM-Internal-Secret)
    A-->>B: [{bot_token, api_key, allowed_user_ids}, ...]
    B->>B: diff vs running, start/stop dispatchers
```

## Where each component lives

| Component | Path |
|---|---|
| Bot container | `telegram-bot/` |
| Bot menu + handlers | `telegram-bot/bot/menu.py`, `telegram-bot/bot/handlers.py` |
| Bot multi-channel loader | `telegram-bot/bot/channels.py` |
| IM channels backend router | `api/routes/im_channels.py` |
| IM channels service (encrypt + Redis pub) | `api/services/im/channel_service.py` |
| Web-call link signer | `api/services/im/web_call_link.py` |
| Telegram-specific api routes | `api/routes/telegram.py` |
| IM channels UI page | `ui/src/app/channels/im/page.tsx` |
| Sidebar entry | `ui/src/components/layout/AppSidebar.tsx` (`IM Channels`) |
| DB models | `api/db/models.py` → `ImChannelModel` |
| Alembic migrations | `api/alembic/versions/a4b5c6d7e8f9_telegram_im_tables.py`, `b5c6d7e8f9a0_im_channels.py` |
| Architecture decisions | `docs/adr/ADR-100..103` |
