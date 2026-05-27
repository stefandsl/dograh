#!/usr/bin/env bash
# Container entrypoint: substitute env vars into Asterisk configs that don't
# natively support interpolation, then start Asterisk in foreground.
set -euo pipefail

: "${ARI_PASSWORD:?ARI_PASSWORD must be set}"
: "${MESSAGENET_USER:?MESSAGENET_USER must be set (SIP URI user part)}"
: "${MESSAGENET_PASSWORD:?MESSAGENET_PASSWORD must be set}"

# Work on a writable copy so /etc/asterisk can be mounted read-only.
RUNTIME_DIR=/etc/asterisk-runtime
mkdir -p "${RUNTIME_DIR}/conf.d"
cp -R /etc/asterisk-src/. "${RUNTIME_DIR}/"

# Render ari.conf
sed -i "s|__ARI_PASSWORD__|${ARI_PASSWORD}|g" "${RUNTIME_DIR}/ari.conf"

# Render messagenet trunk config from the .example template if the operator
# didn't supply a real local file. This is fine for an initial boot — the
# trunk registration will fail until real credentials are supplied, but
# Asterisk itself will come up healthy.
LOCAL_CONF="${RUNTIME_DIR}/conf.d/messagenet_local.conf"
if [ ! -f "${LOCAL_CONF}" ]; then
  cp "${RUNTIME_DIR}/conf.d/messagenet_local.conf.example" "${LOCAL_CONF}"
fi
sed -i "s|__MESSAGENET_USER__|${MESSAGENET_USER}|g" "${LOCAL_CONF}"
sed -i "s|__MESSAGENET_PASSWORD__|${MESSAGENET_PASSWORD}|g" "${LOCAL_CONF}"

# Resolve EXTERNAL_IP for SDP / Contact rewriting. Required when Asterisk
# runs in a docker bridge network so the carrier can reach us for RTP.
# Operator can pin it via the EXTERNAL_IP env var; otherwise we ask a
# public echo service. Fall back to the container's primary IP only if
# both fail — useful for in-network testing but not for live trunks.
if [ -z "${EXTERNAL_IP:-}" ]; then
  EXTERNAL_IP="$(curl -fsS --max-time 3 https://api.ipify.org 2>/dev/null || true)"
fi
if [ -z "${EXTERNAL_IP:-}" ]; then
  EXTERNAL_IP="$(hostname -I | awk '{print $1}')"
  echo "[entrypoint] WARNING: EXTERNAL_IP not set and public lookup failed;" \
       "falling back to container IP ${EXTERNAL_IP}. RTP from MessageNet" \
       "will not be reachable."
fi
echo "[entrypoint] Using EXTERNAL_IP=${EXTERNAL_IP} for PJSIP SDP/Contact rewriting"
sed -i "s|__EXTERNAL_IP__|${EXTERNAL_IP}|g" "${RUNTIME_DIR}/pjsip.conf"

# Point Asterisk at the rendered config dir.
exec asterisk -f -C "${RUNTIME_DIR}/asterisk.conf"
