---
title: WhatsApp Cloud API channel
description: Connect a WhatsApp Business number to a Dograh workflow via Meta's Cloud API.
---

# WhatsApp Cloud API channel

Connect a WhatsApp Business number to a Dograh workflow using Meta's
[WhatsApp Business Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api).
Once configured, inbound WhatsApp messages are normalised, routed to the
same text-chat runtime the Telegram channel and in-UI tester use, and the
agent's reply is sent back to the user.

## Architecture

```
WhatsApp user
   │   (sends a message)
   ▼
Meta Cloud API
   │   POST /api/v1/im/channels/whatsapp/<channel_id>/webhook
   │   X-Hub-Signature-256: sha256=<HMAC>
   ▼
api/routes/im_channels.py:whatsapp_webhook_receive
   │   verify HMAC-SHA256(app_secret, raw body)
   │   parse Meta envelope → InboundMessage
   ▼
api/services/im/whatsapp/dispatcher.py
   │   look up channel by phone_number_id
   │   dedupe by Meta message id
   │   ensure (org, channel, wa_id) session row
   │   ensure workflow_run + text-chat session
   │   append user turn
   │   run pending assistant turn  (api/services/workflow/text_chat_session_service.py)
   ▼
api/services/im/whatsapp/meta_client.send_text
   │   POST graph.facebook.com/<ver>/<pnid>/messages
   ▼
WhatsApp user receives the agent's reply
```

A WhatsApp channel is a row in the `im_channels` table with
`type='whatsapp'`. Credentials live encrypted in `config_encrypted`
(Fernet, key derived from `OSS_JWT_SECRET`). There is **no separate
WhatsApp bot container** — Meta delivers messages over HTTPS webhooks,
which the api container receives directly. This is the principal
difference from Telegram, which long-polls from its own process.

## What you need from Meta

Provision these in the [Meta Developer Console](https://developers.facebook.com/):

1. A **Meta App** (Business type) — the App ID and **App Secret** live
   under *App Settings → Basic*.
2. A **WhatsApp Business Account** (WABA) attached to the app.
3. A **phone number** in that WABA (Meta gives you a test number to
   start; production numbers require business verification).
4. A **system user access token** with `whatsapp_business_messaging` +
   `whatsapp_business_management` permissions. Long-lived tokens are
   preferred over the 24-hour temporary one from the API Setup screen.

From those you'll need to know:

| Field | Where to find it |
|---|---|
| `phone_number_id` | *WhatsApp → API Setup → Phone number ID*. Numeric string, not the human-readable phone number. |
| `access_token` | *WhatsApp → API Setup → Temporary access token* (testing) or *Business Settings → System users → Generate token* (production). |
| `app_secret` | *App Settings → Basic → App Secret* (click "Show"). Used to verify webhook signatures. |
| `verify_token` | A string you pick. Dograh's UI has a **Generate** button that produces a 32-hex string. |
| `business_account_id` *(optional)* | *WhatsApp → API Setup → WhatsApp Business Account ID*. Currently informational. |
| `graph_version` | The Graph API version you want to pin (default `v20.0`). |

## Step-by-step

### 1. Configure the channel in Dograh

1. Open the Dograh UI → **Settings → IM Channels** (`/channels/im`).
2. Click the **WhatsApp** tab → **+ Add WhatsApp number**.
3. Fill in the fields. Use **Generate** for the verify token unless you
   already have one you want to use. The dialog also asks for an
   optional WABA id and the Graph version.
4. Save. The card shows the channel's public webhook URL — a
   fully-qualified URL derived from your `DOGRAH_PUBLIC_URL`
   (e.g. `https://example.com/api/v1/im/channels/whatsapp/3/webhook`).

### 2. Subscribe Meta to that webhook URL

1. Back in Meta Developer Console: *WhatsApp → Configuration*.
2. **Callback URL**: paste the URL from the Dograh card.
3. **Verify token**: paste the same verify token you set in Dograh.
4. Click **Verify and save**. Meta will issue a `GET` to your URL with
   `hub.mode=subscribe&hub.verify_token=…&hub.challenge=…`; Dograh's
   handler looks up the channel by id, compares the verify token, and
   echoes back the challenge as plain text. On success the button turns
   green.
5. Under **Webhook fields**, subscribe to the **`messages`** field at
   minimum. (Subscribing to `message_template_status_update` is
   harmless — Dograh currently logs and ignores it.)

### 3. Test the connection

1. In the Dograh UI, on the WhatsApp channel card, click **Test
   connection**. Dograh hits the Graph API with the stored access token
   and reports the verified business name + phone number.
2. From your own WhatsApp client, send "hello" to the business number.
   You should see the agent reply within a few seconds. Check the api
   container logs for `[whatsapp/dispatch]` lines — they trace the
   dedupe, workflow-run resolution, and outbound send.

## How active workflow is picked

If the WhatsApp session has no `workflow_id` yet (first message ever
from that contact), Dograh picks the org's *first active workflow* by
alphabetical name. A per-conversation `/workflows` style switcher is a
planned follow-up; for now, set the order of workflows in the UI to
control the default.

The chosen workflow is sticky per `(organisation_id, channel_id,
wa_id)` — once a conversation has bound to a workflow, all future
messages from that contact go to the same workflow until an admin
unbinds it (via SQL today: `UPDATE whatsapp_sessions SET workflow_id =
NULL WHERE wa_id = '…'` — a UI control is on the roadmap).

## What's supported (and what isn't yet)

| | Status |
|---|---|
| Inbound text → workflow → outbound text | ✅ |
| Webhook signature verification (HMAC-SHA256 / app secret) | ✅ |
| Webhook GET handshake | ✅ |
| Per-channel encrypted credentials | ✅ |
| Per-message dedupe (Meta retries) | ✅ |
| Outbound `send_text` (free-form, within 24h window) | ✅ |
| Outbound `send_template` (pre-approved templates, vars) | ✅ (client-side; UI surfaces will follow) |
| Outbound `send_media` (image / audio / video / document) | ✅ (client-side; not yet wired to the dispatcher) |
| Inbound media (audio/voice notes via STT, images, docs) | ❌ — parser extracts metadata, but the dispatcher replies with a "text only for now" hint. Telegram-style Whisper STT will be ported to this channel as a follow-up. |
| Delivery status persistence | ❌ — statuses are logged at INFO but not written to a table. |
| Multi-workflow per contact (switch on the fly) | ❌ — single workflow per session. |
| ARQ background processing for the LLM turn | ❌ — dispatcher runs the turn synchronously inside the webhook handler. Acceptable while p50 LLM latency stays sub-second; move to a background queue when that's no longer true. |

## Security notes

- The webhook endpoint is **public** (it cannot be Bearer-token-gated
  because Meta won't send a token). Defence is the HMAC-SHA256
  signature, validated against each channel's `app_secret`. Requests
  with a missing or wrong signature get a 403 and are not parsed.
- Signature comparison uses `hmac.compare_digest` (constant-time).
- Tokens are never logged. The Meta outbound client redacts the request
  body before any warning log; it only logs the URL, the HTTP status,
  and Meta's structured `error` field.
- The `verify_token` is shown plaintext in the UI dialog so the
  operator can paste it into Meta; after save it's masked (last 6 chars)
  in API responses and in the UI card.
- The `IM_INTERNAL_SECRET` and per-channel API key minting the Telegram
  channel uses do **not** apply here. WhatsApp lives entirely inside the
  api container; there's no second process that needs plaintext
  credentials.

## Local testing without Meta

You can drive the webhook from a local script for development:

```bash
# Mint a HMAC-SHA256 signature with the app_secret you configured.
APP_SECRET="paste-your-app-secret-here"
BODY='{"object":"whatsapp_business_account","entry":[{"id":"WABA_ID","changes":[{"field":"messages","value":{"messaging_product":"whatsapp","metadata":{"phone_number_id":"PNID-123"},"messages":[{"from":"393450000000","id":"wamid.local-test-1","timestamp":"1717000000","type":"text","text":{"body":"hello"}}]}}]}]}'
SIG="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$APP_SECRET" -hex | sed 's/.* //')"

# Replace 3 with your channel id, and the host with your DOGRAH_PUBLIC_URL.
curl -i -X POST "$DOGRAH_PUBLIC_URL/api/v1/im/channels/whatsapp/3/webhook" \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$BODY"
```

The response is `200 OK {"status":"ok"}`. The dispatcher logs trace the
flow; the agent's reply goes to the Meta Cloud API outbound endpoint
(which will fail in a local dev with a sandbox token, but the inbound
plumbing will have been exercised end-to-end).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Meta's "Verify and save" fails with **HTTP 403** | The verify token in Dograh and in Meta don't match, or the channel is disabled. |
| Meta delivers messages but Dograh logs `bad signature` | The app secret in Dograh and in Meta don't match. Re-copy from *App Settings → Basic → App Secret*. |
| `no enabled channel for phone_number_id=…` log line | The `phone_number_id` Meta sent doesn't match any enabled channel row. Check the value in the UI vs Meta's API Setup screen. |
| Meta replies with code **131047** "outside 24h window" | The user hasn't messaged you in 24h. Send a pre-approved template via `send_template` instead of free-form text. |
| Replies arrive duplicated | The dispatcher dedupes by Meta `message_id`. If you see duplicates, look at the message ids in the logs — they should differ; if they don't, Meta is sending true retries and the deduper is dropping them silently. |

## Reference

- [WhatsApp Cloud API — Inbound webhooks](https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples)
- [WhatsApp Cloud API — Messages endpoint](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages)
- [WhatsApp Cloud API — Webhook security](https://developers.facebook.com/docs/graph-api/webhooks/getting-started#validating-payloads)
- Source: `api/services/im/whatsapp/`, `api/routes/im_channels.py`,
  `api/alembic/versions/c7e8f9a0b1c2_whatsapp_im_tables.py`,
  `ui/src/app/channels/im/page.tsx`,
  `ui/src/lib/imChannels.ts`.
