# Merge status — CliClaw → Dograh

| Phase | PR | Status | Notes |
|---|---|---|---|
| 0 — Research + ADRs | #10 | 🟢 merged | 4 ADRs, 2 maps. |
| 1 — Scaffold | #11 | 🟢 merged | Container + compose profile + healthcheck. |
| 2 — Port core | #12 | 🟢 merged | Dograh API client + Postgres FTS migration + bootstrap dispatcher. |
| 3 — Voice | #13 | 🟢 merged | Fernet web-call link + voice-note STT (Groq Whisper). |
| 4a — IM channels backend | #14 | 🟢 merged | Model + Alembic + service + router + encryption. |
| 4c — Bot multi-loader | #15 | 🟢 merged | `TelegramChannelManager`, diff-reload, Redis subscriber. |
| 4b — UI IM Channels | #16 | 🟢 merged | Next.js page + sidebar entry + hand-rolled fetch helper. |
| 5 — Syntx menu | #17 | 🟢 merged | 9 buttons, all wired. Chat + Memory + Workflows fully functional. |
| 7 — Docs | #18 | 🟢 merged | README + `docs/channels/telegram.md` + `docs/channels/architecture.md`. |
| 6 — Installer | #19 | 🟢 merged | Minimal interactive `install.sh` — strictly additive. |
| 8 — E2E CI | #20 | 🟢 merged | `telegram-bot-tests.yml` + `e2e-smoke.yml` + `docker-compose-test.yaml` + `tests/e2e/run.sh`. |
| 8 — CI fixes | #21, #22 | 🟢 merged | Retry on transient pulls + build api from source so the new routes exist. |
| 9 — Cleanup | this PR | 🟢 in flight | Remote + local feature branches pruned. |
| 9 — Release tag | — | 🟡 blocked | `release-please` workflow needs a token in the fork's repo secrets (Input required and not supplied: token). Configure GH_RELEASE_TOKEN (or whatever the upstream secret is called) on stefandsl/dograh, or run `gh release create` manually. |
| 9 — Archive CliClaw | — | 🔴 needs explicit consent | Destructive action on the separate `stefandsl/CliClaw` repo. Awaiting user's "yes archive CliClaw". |

## Cumulative deliverables

- 14 PRs merged (#10–#22) — 13 feature/fix + this status PR
- Working Telegram channel: container + compose profile + UI page + multi-bot loader with hot-reload + 9-button menu
- Two GitHub Actions workflows for the new code
- Interactive installer that's strictly additive (doesn't break the old curl one-liner)
- Setup walkthrough + architecture diagrams in `docs/channels/`
- 4 ADRs documenting the architectural decisions

## Known follow-ups (documented in-code, not silent fails)

- `npm run generate-client` in `ui/` once Phase 4a routes are deployed → swap `ui/src/lib/imChannels.ts` to typed SDK calls
- Phase 5 deferred: APScheduler runner for `telegram_scheduled_tasks`; per-chat settings; image-qa workflow upload path
- Phase 3 deferred: TTS-out for voice notes (need chat-with-run streaming)
- Phase 8 deferred: full Telegram-test-server scenarios (need real test bot token or local tdlib server)
- Per-channel org-id plumbing through the bot handler context (currently env-driven via `MESSAGENET_FALLBACK_ORG_ID`)
