#!/usr/bin/env bash
# First-boot configuration script.
# Reads /boot/firmware/signage.conf, writes /etc/signage/config,
# substitutes SIGNAGE_API_URL into systemd user unit files,
# then restarts the signage user services.
set -euo pipefail

PRESEED="/boot/firmware/signage.conf"
CONFIG_DIR="/etc/signage"
CONFIG_FILE="${CONFIG_DIR}/config"
UNIT_DIR="/home/signage/.config/systemd/user"
SIGNAGE_UID=$(id -u signage 2>/dev/null || echo "")

log() { echo "[firstboot] $*" | tee /dev/kmsg 2>/dev/null || echo "[firstboot] $*"; }

log "=== Signage first-boot starting ==="

# --- Read preseed ---
if [ ! -f "${PRESEED}" ]; then
  log "ERROR: ${PRESEED} not found. Cannot configure. Sidecar will not start."
  exit 1
fi

# Source the preseed (plain key=value, no export needed)
set -a
# shellcheck source=/dev/null
source "${PRESEED}"
set +a

if [ -z "${SIGNAGE_API_URL:-}" ]; then
  log "ERROR: SIGNAGE_API_URL not set in ${PRESEED}. Edit ${PRESEED} and reboot."
  exit 1
fi

log "SIGNAGE_API_URL=${SIGNAGE_API_URL}"

# --- Write /etc/signage/config ---
install -d -m 0755 "${CONFIG_DIR}"
cat > "${CONFIG_FILE}" <<EOF
# Written by signage-firstboot.service on $(date -u +%Y-%m-%dT%H:%M:%SZ)
SIGNAGE_API_URL=${SIGNAGE_API_URL}
EOF
chmod 0644 "${CONFIG_FILE}"
log "Wrote ${CONFIG_FILE}"

# --- Substitute URL in unit files ---
if [ -z "${SIGNAGE_UID:-}" ]; then
  log "ERROR: signage user not found. Image may be corrupted."
  exit 1
fi

for UNIT in labwc.service signage-sidecar.service signage-player.service; do
  UPATH="${UNIT_DIR}/${UNIT}"
  if [ -f "${UPATH}" ]; then
    sed -i "s|__SIGNAGE_API_URL__|${SIGNAGE_API_URL}|g" "${UPATH}"
    log "Patched ${UNIT}"
  else
    log "WARNING: ${UPATH} not found"
  fi
done

# --- Reload and restart user services ---
XDG_RUNTIME_DIR="/run/user/${SIGNAGE_UID}"
DBUS_ADDR="unix:path=${XDG_RUNTIME_DIR}/bus"

# Ensure user manager is running (loginctl enable-linger already created the file)
systemctl start "user@${SIGNAGE_UID}.service" || log "WARNING: user@${SIGNAGE_UID} already running"

for _ in $(seq 1 20); do
  [ -S "${XDG_RUNTIME_DIR}/bus" ] && break
  sleep 0.5
done

sudo -u signage \
  XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR}" \
  DBUS_SESSION_BUS_ADDRESS="${DBUS_ADDR}" \
  systemctl --user daemon-reload || log "WARNING: daemon-reload failed"

sudo -u signage \
  XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR}" \
  DBUS_SESSION_BUS_ADDRESS="${DBUS_ADDR}" \
  systemctl --user restart signage-sidecar.service signage-player.service || \
  log "WARNING: service restart failed; services will start on next boot"

# --- Optional: set hostname if SIGNAGE_HOSTNAME is set ---
if [ -n "${SIGNAGE_HOSTNAME:-}" ]; then
  hostnamectl set-hostname "${SIGNAGE_HOSTNAME}"
  log "Hostname set to ${SIGNAGE_HOSTNAME}"
fi

log "=== First-boot complete. signage-firstboot.service will self-disable. ==="

# Idempotency: remove preseed API URL so second-boot is a no-op
# (Do NOT remove the whole file; leave it as a reference for operators)
sed -i 's|^SIGNAGE_API_URL=.*|# SIGNAGE_API_URL already applied — edit and reboot to re-apply|' \
  "${PRESEED}" 2>/dev/null || true
