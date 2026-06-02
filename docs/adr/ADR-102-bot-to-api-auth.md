# ADR-102 — Bot ↔ Bellerophone API authentication

**Status:** Accepted
**Date:** 2026-05-27
**Context:** Phase 0. The Telegram bot container needs to call the
Bellerophone FastAPI service as a service-to-service client. It also has to
act on behalf of a specific Bellerophone user (the one who owns the workflow
the Telegram message targets).

## Decision

**Use Bellerophone's existing `X-API-Key` mechanism with per-org service-account
keys, scoped via the IM channel row.**

Concretely:

1. The IM channel record stored in the `im_channels` table (Phase 4)
   contains the Telegram bot token AND a reference to a Bellerophone API key
   row. When an admin enables a Telegram channel in the UI, the backend
   either:
   - Reuses an existing API key the admin selects, or
   - Auto-mints a new key in the same org with a service-account name
     (`telegram-bot/<chat-or-org>`) and a fixed scope claim
     (`scope=im:telegram`).
2. The bot container loads `(bot_token, api_key)` pairs from
   `GET /api/v1/im/channels?type=telegram&enabled=true` at boot and on
   Redis pub/sub (`im:channels:reload`) — see Phase 4. The api_key is
   used as `X-API-Key: <key>` on every subsequent Bellerophone API call by
   that bot.
3. The bot never authenticates as the end-user (the Telegram chat
   participant). It maps `(telegram_chat_id, bot_id)` → an org via the
   IM channel row, and operates entirely under that org's
   service-account.

## Why not JWT

JWT is fine for first-party browser flows but creates a refresh problem
for a long-lived bot container. Pre-issued, revocable API keys are
operationally simpler and Bellerophone already supports them
(`api/routes/user_api_keys.py` + `X-API-Key` middleware in
`api/services/auth/depends.py:19-129`).

## Why not "anonymous internal" via a shared secret

A shared secret would skip org scoping and require us to invent a
parallel auth surface. Reusing the API-key path means every Bellerophone
endpoint already enforces org isolation correctly without further
work — important for multi-tenant.

## Implications

- The IM channels `POST` route auto-creates the API key (or accepts an
  existing one) and stores its id, not the plaintext.
- Plaintext API key is only available to the bot container at the
  moment it loads the channel — fetched via the IM channels
  `/secret-bundle` sub-endpoint, gated by the api's own JWT (only
  service tokens with the `im:channels:read-secrets` claim can call it).
- Token rotation: `PATCH /api/v1/im/channels/telegram/{id}/rotate-api-key`
  mints a new key, returns the new value, and publishes
  `im:channels:reload` so the bot picks it up within one Redis tick.
- This is multi-tenant by construction: bot container holds a token
  for each enabled IM channel; each call is scoped to the right org.

## Future

If we ever wire a *user-side* OAuth flow ("link my Telegram to my
Bellerophone account"), we'll layer it on top of this: the IM channel still
holds the service key for the org, plus a `linked_users` table maps
`telegram_user_id` → `dograh_user_id`. Out of scope for the merge.
