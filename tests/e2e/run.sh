#!/usr/bin/env bash
# E2E smoke for the Telegram channel stack.
#
# Brings up the full docker-compose stack with the test overrides, waits
# for healthchecks, hits the new IM-channels surface, tears down.
# Designed for ~2-3 min in GitHub Actions; verifies the wiring across
# api ↔ Postgres ↔ Redis ↔ telegram-bot without needing a real Telegram
# bot token (the bot runs in health-only mode under these overrides).
set -euo pipefail

cd "$(dirname "$0")/../.."

COMPOSE="docker compose -f docker-compose.yaml -f docker-compose-test.yaml"

cleanup() {
  echo "==> Tearing down"
  $COMPOSE --profile telegram down -v || true
}
trap cleanup EXIT

echo "==> Building telegram-bot image"
$COMPOSE --profile telegram build telegram-bot

echo "==> Bringing the stack up (retries on transient registry errors)"
attempt=0
until $COMPOSE --profile telegram up -d; do
  attempt=$((attempt + 1))
  if [[ $attempt -ge 3 ]]; then
    echo "==> compose up failed 3 times, giving up"
    exit 1
  fi
  echo "==> compose up failed (attempt $attempt/3); sleeping 10s before retry"
  $COMPOSE --profile telegram down -v || true
  sleep 10
done

wait_for() {
  # wait_for <label> <command>  → retries the command until it succeeds
  # or hits the per-call ~60s budget.
  local label="$1"; shift
  for i in $(seq 1 30); do
    if "$@" >/dev/null 2>&1; then
      echo "==> $label OK"
      return 0
    fi
    sleep 2
  done
  echo "==> $label TIMEOUT"
  return 1
}

echo "==> Waiting for api"
wait_for "api /api/v1/health" curl -fsS http://localhost:8000/api/v1/health

echo "==> Waiting for telegram-bot /healthz"
wait_for "telegram-bot /healthz" \
  docker exec dograh-telegram-bot curl -fsS http://localhost:8080/healthz

echo "==> Asserting secret-bundle endpoint refuses bad secret"
status=$(curl -s -o /dev/null -w '%{http_code}' \
  -H 'X-IM-Internal-Secret: wrong' \
  http://localhost:8000/api/v1/im/channels/secret-bundle || true)
if [[ "$status" != "401" ]]; then
  echo "expected 401, got $status"
  exit 1
fi
echo "==> 401 on bad secret OK"

echo "==> Asserting secret-bundle endpoint accepts good secret"
body=$(curl -fsS \
  -H 'X-IM-Internal-Secret: ci-only-im-internal-secret' \
  http://localhost:8000/api/v1/im/channels/secret-bundle)
if [[ "$body" != "[]" ]]; then
  echo "expected empty bundle on a fresh deployment, got: $body"
  exit 1
fi
echo "==> empty bundle on fresh deploy OK"

echo "==> Asserting bot is in multi-channel mode (no token in env)"
docker logs dograh-telegram-bot 2>&1 | grep -q "multi-channel mode online" \
  || { echo "bot didn't enter multi-channel mode"; exit 1; }
echo "==> bot log shows multi-channel mode OK"

echo
echo "✅ E2E smoke passed"
