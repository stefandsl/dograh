# PHASE 6 — Interactive install.sh

**Branch:** `feat/merge-cliclaw-phase-6`

## Goal
Replace the current curl-the-compose-file install instructions with an interactive bash installer that asks whether to enable the Telegram channel.

## Existing
README currently says:
```bash
curl -o docker-compose.yaml https://.../docker-compose.yaml \
  && REGISTRY=ghcr.io/dograh-hq ENABLE_TELEMETRY=true \
  docker compose up --pull always
```

## New
```bash
curl -fsSL https://raw.githubusercontent.com/dograh-hq/dograh/main/install.sh \
  -o /tmp/dograh-install.sh && sudo bash /tmp/dograh-install.sh
```

## install.sh behaviour
1. Check Docker + Compose v2 present.
2. Download `docker-compose.yaml` into the target dir.
3. Interactive prompt: "Enable Telegram bot channel? [y/N]"
   - If `y`: prompt `BOT_TOKEN`, `ALLOWED_USER_IDS` (csv).
4. Generate `.env` with all values + `COMPOSE_PROFILES=` joined from selections (e.g. `telegram,messagenet`).
5. `docker compose --pull always up -d`.
6. Health-wait: `curl api:8000/health` + UI `:3010`.
7. Print success summary: UI URL, bot username (if Telegram), useful commands.

## Flags
- `--reconfigure` — re-runs prompts on an existing install, overwrites .env, restarts only changed services
- `--upgrade` — `git pull` (if cloned) + `docker compose pull` + restart
- `--dry-run` — print every command, execute none

Idempotent: re-running without flags is a no-op if .env exists and services are healthy.

## Docs
`docs/deployment/install.md` walks through every prompt with screenshots / asciinema if possible.

## Verifier
- `shellcheck install.sh` clean.
- `--dry-run` prints sane plan.
- In Docker-in-Docker on Debian 12: full install <5 min, healthchecks green.
- `--reconfigure` flow tested by changing BOT_TOKEN and confirming bot picks up the new value.
- `--upgrade` flow tested by bumping image tag and confirming new container is running.
