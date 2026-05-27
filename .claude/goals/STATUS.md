# Merge status — CliClaw → Dograh

| Phase | Branch / PR | Status | Notes |
|---|---|---|---|
| 0 — Research + ADRs | #10 | 🟢 merged | 4 ADRs, 2 maps. ADR-101 corrected the master plan (Path A unimplementable). |
| 1 — Scaffold | #11 | 🟢 merged | Container + compose profile + healthcheck. |
| 2 — Port core | #12 | 🟢 merged | Dograh API client + Postgres FTS migration + bootstrap dispatcher. |
| 3 — Voice | #13 | 🟢 merged | Fernet web-call link + voice-note STT (Groq Whisper). TTS-out deferred. |
| 4a — IM channels backend | #14 | 🟢 merged | `ImChannelModel` + Alembic + service + router + Fernet + Redis pub. |
| 4c — Bot multi-loader | #15 | 🟢 merged | `TelegramChannelManager`, diff-reload, Redis subscriber. |
| 4b — UI IM Channels | #16 | 🟢 merged | Next.js page + sidebar entry + hand-rolled fetch helper (TODO: regenerate SDK). |
| 5 — Syntx menu | #17 | 🟢 merged | 9 buttons, all wired. Chat + Memory + Workflows fully functional; Scheduler/Settings/Images stubbed with helpful guidance, no silent fails. |
| 6 — Installer | — | 🟡 needs sign-off | Rewrites public install path; **destructive-adjacent**. Don't auto-merge. |
| 7 — Docs | (this PR) | 🟢 in flight | README section, `docs/channels/telegram.md`, `docs/channels/architecture.md`. CHANGELOG auto-managed by release-please. |
| 8 — E2E CI | — | ⏳ pending | docker-compose-test.yaml + GH Actions + Telegram test server. Largest remaining piece. |
| 9 — Release + archive CliClaw | `main` | ⏳ pending | Tag + branch prune. CliClaw archive requires explicit user consent. |
