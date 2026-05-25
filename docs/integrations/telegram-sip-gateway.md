# Telegram SIP Gateway

Telegram does **not** support SIP natively. Dograh integrates with an **external SIP↔Telegram gateway** (e.g. [SIP.TG](https://sip.tg), tg2sip, or your own REST bridge) so admins can place and receive calls routed to a Telegram account.

## Configuration

In the UI: **Telegram SIP** (sidebar under BUILD), or via API:

- `GET/POST /api/v1/organizations/telegram-sip-gateway/configs`
- `PUT/DELETE /api/v1/organizations/telegram-sip-gateway/configs/{id}`
- `POST /api/v1/organizations/telegram-sip-gateway/configs/{id}/test` — connectivity check

Required fields:

| Field | Description |
|-------|-------------|
| `sip_host` / `sip_port` | SIP registrar or trunk host |
| `sip_username` / `sip_password` | SIP credentials (stored masked; never logged) |
| `sip_caller_id` | Caller ID / SIP number presented to the gateway |
| `telegram_destination_id` | Telegram username, phone, or routing ID for the gateway |
| `gateway_provider_type` | `sip_tg`, `tg2sip`, or `custom` |
| `gateway_api_base_url` | REST base URL for the external gateway |

Optional: `webhook_callback_url`, `gateway_api_key`.

## Outbound calls

`POST /api/v1/organizations/telegram-sip-gateway/configs/{id}/calls`

```json
{ "destination": "@username" }
```

Returns a call log row with status (`ringing`, `connected`, `failed`, `completed`, etc.).

## Gateway webhooks (public)

Register these URLs with your gateway (replace `{config_id}` and `{backend}`):

- **Inbound SIP:** `POST {backend}/api/v1/telegram-sip-gateway/webhooks/{config_id}/incoming`
- **Status updates:** `POST {backend}/api/v1/telegram-sip-gateway/webhooks/{config_id}/status`

Status payload example:

```json
{
  "call_id": "gateway-call-uuid",
  "status": "completed",
  "error_code": null,
  "error_message": null
}
```

## Custom gateway REST contract

When using `custom` (or pointing `sip_tg` / `tg2sip` at a compatible API), the gateway should implement:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `{base}/test` | Validate SIP credentials |
| `POST` | `{base}/calls` | Start outbound call; return `{ "call_id", "status" }` |
| `GET` | `{base}/calls/{id}` | Poll call status |
| `POST` | `{base}/incoming` | Route inbound SIP to `telegram_destination_id` |

Request bodies include SIP fields and `telegram_destination_id` (passwords must not appear in Dograh logs).

## Database

Migration `f8a2b3c4d5e6` creates:

- `telegram_sip_gateway_configurations`
- `telegram_sip_call_logs`

Run: `alembic upgrade head` from `api/`.

## Architecture

- `TelegramSipGatewayProvider` — provider interface
- `CustomSipTelegramGatewayProvider` — HTTP client for the contract above
- `TelegramSipService` — orchestration, call logs, lifecycle logging

Standard Dograh telephony (Twilio, ARI, Pipecat) is unchanged.
