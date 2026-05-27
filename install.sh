#!/usr/bin/env bash
# Dograh interactive installer.
#
# Minimal wrapper around the existing curl-the-compose-file pattern that
# also offers to enable the Telegram IM channel (Phase 1-5 of the
# CliClaw merge). Idempotent: re-running on an existing install is safe
# — env values are kept from .env unless you pass --reconfigure.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/dograh-hq/dograh/main/install.sh \
#     -o /tmp/dograh-install.sh && bash /tmp/dograh-install.sh
#
# Flags:
#   --no-telegram     skip the Telegram prompt, install api+ui only
#   --with-telegram   prefill yes for the Telegram prompt (still asks
#                     for BOT_TOKEN if missing)
#   --reconfigure     re-prompt for values even if they're already in .env
#   --dry-run         print docker compose commands without executing them
#
# Env passthrough (set before running to skip prompts):
#   REGISTRY              default: ghcr.io/dograh-hq
#   ENABLE_TELEMETRY      default: true
#   TELEGRAM_BOT_TOKEN    if set, --with-telegram is implied
#   TELEGRAM_ALLOWED_USERS    comma-separated Telegram user IDs
#   IM_INTERNAL_SECRET    if set, the script reuses it; otherwise a
#                         32-byte hex secret is generated
set -euo pipefail

# ---------- defaults & flags ----------------------------------------------
REGISTRY="${REGISTRY:-ghcr.io/dograh-hq}"
ENABLE_TELEMETRY="${ENABLE_TELEMETRY:-true}"
ENABLE_TELEGRAM_DEFAULT=""   # "" → ask, "y" → prefill yes, "n" → skip
RECONFIGURE=0
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --no-telegram)    ENABLE_TELEGRAM_DEFAULT=n ;;
    --with-telegram)  ENABLE_TELEGRAM_DEFAULT=y ;;
    --reconfigure)    RECONFIGURE=1 ;;
    --dry-run)        DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,30p' "$0" | sed 's/^# //; s/^#//'
      exit 0 ;;
    *)
      echo "unknown flag: $arg (see --help)" >&2
      exit 2 ;;
  esac
done

[[ -n "${TELEGRAM_BOT_TOKEN:-}" && -z "$ENABLE_TELEGRAM_DEFAULT" ]] && ENABLE_TELEGRAM_DEFAULT=y

run() {
  if [[ $DRY_RUN -eq 1 ]]; then
    printf '+ %s\n' "$*"
  else
    eval "$*"
  fi
}

prompt() {
  # prompt VAR "Label" ["default"]
  local var="$1" label="$2" def="${3:-}"
  local cur="${!var:-$def}"
  if [[ -t 0 ]]; then
    local input
    if [[ -n "$cur" ]]; then
      read -r -p "$label [$cur]: " input || true
      input="${input:-$cur}"
    else
      read -r -p "$label: " input || true
    fi
    printf -v "$var" '%s' "$input"
  else
    printf -v "$var" '%s' "$cur"
  fi
}

confirm() {
  # confirm "Label" "default-y-or-n"
  local label="$1" def="${2:-n}" ans
  if [[ ! -t 0 ]]; then
    printf '%s\n' "$def"; return
  fi
  read -r -p "$label [$([[ $def == y ]] && echo Y/n || echo y/N)]: " ans || true
  ans="${ans:-$def}"
  case "${ans,,}" in
    y|yes) printf 'y\n' ;;
    *)     printf 'n\n' ;;
  esac
}

# ---------- preflight ----------------------------------------------------
command -v docker >/dev/null 2>&1 \
  || { echo "❌ docker not found in PATH" >&2; exit 1; }
docker compose version >/dev/null 2>&1 \
  || { echo "❌ 'docker compose' (v2) not found" >&2; exit 1; }

echo "==> Dograh installer (registry=$REGISTRY, telemetry=$ENABLE_TELEMETRY)"

# ---------- compose file -------------------------------------------------
if [[ ! -f docker-compose.yaml || $RECONFIGURE -eq 1 ]]; then
  echo "==> Downloading docker-compose.yaml"
  run "curl -fsSL https://raw.githubusercontent.com/dograh-hq/dograh/main/docker-compose.yaml -o docker-compose.yaml"
fi

# ---------- .env merge ---------------------------------------------------
touch .env
preserve_env() {
  # If KEY=… is missing from .env, append KEY=value.
  local key="$1" val="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then return; fi
  printf '%s=%s\n' "$key" "$val" >> .env
}
preserve_env REGISTRY "$REGISTRY"
preserve_env ENABLE_TELEMETRY "$ENABLE_TELEMETRY"

# ---------- telegram opt-in ---------------------------------------------
PROFILES=()
if [[ -z "$ENABLE_TELEGRAM_DEFAULT" ]]; then
  ENABLE_TELEGRAM_DEFAULT="$(confirm 'Enable the Telegram bot channel?' n)"
fi

if [[ "$ENABLE_TELEGRAM_DEFAULT" == "y" ]]; then
  echo "==> Telegram channel enabled"
  prompt TELEGRAM_BOT_TOKEN "  Bot token from @BotFather"
  prompt TELEGRAM_ALLOWED_USERS "  Allowed Telegram user IDs (comma-separated, empty = anyone)"
  if [[ -z "${IM_INTERNAL_SECRET:-}" ]]; then
    if command -v openssl >/dev/null 2>&1; then
      IM_INTERNAL_SECRET="$(openssl rand -hex 32)"
    else
      IM_INTERNAL_SECRET="$(head -c 32 /dev/urandom | xxd -p)"
    fi
    echo "  Generated IM_INTERNAL_SECRET (32 hex bytes)"
  fi
  preserve_env IM_INTERNAL_SECRET "$IM_INTERNAL_SECRET"
  preserve_env TELEGRAM_BOT_TOKEN "${TELEGRAM_BOT_TOKEN:-}"
  preserve_env TELEGRAM_ALLOWED_USERS "${TELEGRAM_ALLOWED_USERS:-}"
  PROFILES+=("telegram")
fi

# ---------- compose up ---------------------------------------------------
profile_args=""
for p in "${PROFILES[@]}"; do
  profile_args+=" --profile $p"
done
echo "==> Bringing the stack up"
run "docker compose$profile_args --pull always up -d"

echo
echo "✅ Dograh is starting. First boot can take 2-3 minutes (image pulls)."
echo "   UI:           http://localhost:3010"
echo "   API health:   http://localhost:8000/api/v1/health"
if [[ "$ENABLE_TELEGRAM_DEFAULT" == "y" ]]; then
  echo "   Telegram:     send /start to your bot once it shows up in @BotFather's list"
  echo "                 Configure additional bots in the UI under /channels/im"
fi
echo
echo "Re-run with --reconfigure to re-prompt for env values, or edit .env directly."
