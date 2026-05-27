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

# Point Asterisk at the rendered config dir.
exec asterisk -f -C "${RUNTIME_DIR}/asterisk.conf"
