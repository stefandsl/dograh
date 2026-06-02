# CliClaw import map (what survives the merge)

Source: `https://github.com/stefandsl/CliClaw` (cloned to `/tmp/cliclaw`
during Phase 0 research, read-only).

## Verdict per file

### KEEP-AS-IS (drop into `telegram-bot/bot/` unchanged)

| File | Why |
|---|---|
| `bot/formatting.py` | Markdown → Telegram HTML converter, no backend coupling |
| `bot/memory/vault.py` | Markdown-file fact storage; works against any FS |
| `bot/memory/__init__.py` | Empty init; trivially keeps |

### KEEP-ADAPT (carry over, rewrite the backend integration only)

| File | Adaptation |
|---|---|
| `bot/main.py` | Replace `runner` calls with `dograh_client` calls; aiogram 3 handler layer is solid |
| `bot/voice.py` | Keep Groq Whisper STT; drop ElevenLabs/Groq TTS — TTS comes from Bellerophone workflow run instead (ADR-101) |
| `bot/memory/search.py` | Rewrite SQLite FTS5 query to Postgres `to_tsvector + GIN` (ADR-103) |
| `bot/memory/hooks.py` | Keep injection/extraction logic; update imports to new memory layer |
| `bot/scheduler.py` | Keep cron-matching logic; replace `workspace/schedules.json` with Postgres `telegram_scheduled_tasks` (Phase 2 schema) |
| `bot/config.py` | Strip backend selector enums (DOGRAH_API_URL + TELEGRAM_BOT_TOKEN are the relevant settings) |

### DROP (do not port)

| File | Reason |
|---|---|
| `bot/runner.py` | Core CLI dispatcher to Claude/Codex/Gemini/Qwen/OpenRouter; replaced wholesale by `dograh_client.py` |
| `bot/backends/__init__.py` | Backend factory for the above |
| `bot/backends/base.py` | Abstract base for CLI subprocess wrappers |
| `bot/backends/claude.py` | Claude Code CLI wrapper |
| `bot/backends/codex.py` | Codex CLI wrapper |
| `bot/backends/gemini.py` | Gemini CLI wrapper |
| `bot/backends/openrouter.py` | OpenRouter HTTP wrapper |
| `bot/db.py` | SQLite WAL + FTS5; sessions move to Postgres per ADR-103 |
| `cliclaw.service` | systemd unit; we ship as a docker compose service instead |
| `install.sh` (CliClaw root) | systemd-based installer; Bellerophone's `install.sh` (Phase 6) prompts for Telegram opt-in instead |

## Framework + storage notes from CliClaw

- **Telegram framework:** aiogram 3.x — confirmed compatible (ADR-100)
- **Memory store:** SQLite WAL + FTS5 virtual index, schema inline in
  `db.py` `_migrate()`. Migrated to Postgres per ADR-103.
- **Scheduler:** custom cron parser (not APScheduler). Reads
  `workspace/schedules.json` every 30 s. We're keeping the matcher,
  replacing the JSON file with a Postgres table. (Could swap to
  APScheduler with the existing SQLAlchemy jobstore in Phase 2 if the
  custom parser turns out to be flaky — TBD during implementation.)
- **Voice:** Groq Whisper STT (`groq` async client). Keep.
- **Inline menus:** 6+ keyboard builders (`build_main_menu`,
  `build_sessions_keyboard`, etc.). Replaced by `bot/menu.py` (Phase 5)
  with the Syntx-style 9-button layout.
- **Filesystem I/O:** photo downloads to `workspace/image_*.jpg`,
  schedules JSON. All replaced by MinIO uploads (photos) + Postgres
  (schedules).

## Bytes-from-CliClaw that survive

- formatting.py (KEEP-AS-IS)
- memory/vault.py (KEEP-AS-IS)
- memory/__init__.py (KEEP-AS-IS)
- voice.py (KEEP-ADAPT)
- memory/search.py (KEEP-ADAPT)
- memory/hooks.py (KEEP-ADAPT)
- scheduler.py (KEEP-ADAPT)
- config.py (KEEP-ADAPT, mostly gutted)
- main.py (KEEP-ADAPT, handlers preserved, runner calls swapped)

Everything else is replaced.
