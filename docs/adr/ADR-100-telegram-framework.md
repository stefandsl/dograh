# ADR-100 — Telegram framework

**Status:** Accepted
**Date:** 2026-05-27
**Context:** Phase 0 of the CliClaw → Dograh merge.

## Decision

Use **aiogram 3.28+** (current stable on PyPI, requires Python `>=3.10, <3.15`).

## Why

- CliClaw already uses aiogram 3.x — porting the existing handler layer is a non-event.
- 3.28 is on Python 3.12 (our container base), no version-pin pain.
- Within 3.0 → 3.28 the surface is additive: minor router/middleware
  reorgs, `Bot` context manager, deprecated `parse_mode` kwargs on `Bot`
  removed in 3.7. None of it affects a fresh greenfield bot.
- Alternative (python-telegram-bot v21) would require rewriting every
  handler signature and FSM call. No gain.

## Implications

- `requirements.txt` pins `aiogram>=3.28,<4`.
- We use Router (not Dispatcher.message decorators at module scope) so
  multi-bot (Phase 4) is straightforward — one `Dispatcher` per loaded
  Telegram token, all sharing the same Router tree.
- Bot context manager (`async with bot:`) is used for short-lived API
  calls in the IM-channels `/test` endpoint (Phase 4).
