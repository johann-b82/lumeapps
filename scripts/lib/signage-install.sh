#!/usr/bin/env bash
# scripts/lib/signage-install.sh
# Shared installer library for:
#   - scripts/provision-pi.sh (runtime, booted Pi, root context)
#   - pi-image/stage-signage/01-run-chroot.sh (build-time, pi-gen chroot)
#
# All functions require root. Source this file; do not execute it directly.
# Set SIGNAGE_BUILD_CONTEXT="chroot" when sourcing from pi-gen stage.
#
# SHARED-LIBRARY CONTRACT:
#   Both callers (runtime provision and chroot build) must produce byte-identical
#   filesystem state for:
#     - /home/signage/.config/systemd/user/{labwc,signage-sidecar,signage-player}.service
#     - /opt/signage/pi-sidecar/.venv/ (identical package versions via requirements.txt)
#     - /var/lib/signage/ and /var/lib/signage/media/ (mode 0700, owned by signage)
#     - /var/lib/systemd/linger/signage (file present = linger enabled)
#     - signage user in groups video,audio,render,input
#
#   The only intentional difference: in the baked image, unit files contain the placeholder
#   __SIGNAGE_API_URL__; the firstboot service replaces this with the real URL from
#   /boot/firmware/signage.conf.
#
#   SIGNAGE_BUILD_CONTEXT flag:
#     (unset or empty) = runtime (booted Pi) — uses loginctl, reads /proc/device-tree, etc.
#     "chroot"         = build-time (pi-gen chroot) — no systemd/logind; uses file-based linger.

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'
_info()  { echo -e "${GREEN}[signage-install]${NC} $*"; }
_warn()  { echo -e "${YELLOW}[signage-install] WARN:${NC} $*"; }
_error() { echo -e "${RED}[signage-install] ERROR:${NC} $*" >&2; }

# Single source-of-truth: read package list from signage-packages.txt (sibling file)
_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mapfile -t SIGNAGE_PACKAGES < <(grep -v '^\s*#' "${_LIB_DIR}/signage-packages.txt" | grep -v '^\s*$')

# SCRIPT_DIR is set by the calling script (provision-pi.sh); used in deploy_systemd_units
# when not in chroot context. If not set, default to lib dir's parent.
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "${_LIB_DIR}/.." && pwd)}"

install_signage_packages() {
  # Signature: install_signage_packages()
  # Installs all required system packages.
  # In chroot context: apt-get update is called unconditionally.
  # In runtime context: same behavior.
  _info "Installing system packages..."
  apt-get update -qq
  apt-get install -y --no-install-recommends "${SIGNAGE_PACKAGES[@]}"
  _info "System packages installed."
}

create_signage_user() {
  # Signature: create_signage_user()
  # Creates 'signage' user with required groups. Idempotent.
  _info "Creating 'signage' user..."
  if id signage >/dev/null 2>&1; then
    usermod -aG video,audio,render,input signage
    _info "User 'signage' exists — group membership updated."
  else
    useradd -m -s /bin/bash -G video,audio,render,input signage
    _info "User 'signage' created."
  fi
  # Ensure .config/systemd/user/ directory tree exists
  install -d -m 0755 -o signage -g signage /home/signage/.config
  install -d -m 0755 -o signage -g signage /home/signage/.config/systemd
  install -d -m 0755 -o signage -g signage /home/signage/.config/systemd/user
}

create_signage_directories() {
  # Signature: create_signage_directories()
  # Creates /var/lib/signage/ (cache, 0700) and /opt/signage/ (0755).
  _info "Creating signage directories..."
  install -d -m 0700 -o signage -g signage /var/lib/signage
  install -d -m 0700 -o signage -g signage /var/lib/signage/media
  install -d -m 0755 -o signage -g signage /opt/signage
  _info "Directories created."
}

deploy_systemd_units() {
  # Signature: deploy_systemd_units <api_url> <signage_uid>
  # Copies scripts/systemd/*.service to /home/signage/.config/systemd/user/
  # Substitutes __SIGNAGE_API_URL__ and __SIGNAGE_UID__ via sed.
  local api_url="${1}"
  local signage_uid="${2}"
  local unit_src_dir

  if [ "${SIGNAGE_BUILD_CONTEXT:-}" = "chroot" ]; then
    unit_src_dir="/opt/signage/scripts/systemd"
  else
    unit_src_dir="${SCRIPT_DIR}/../scripts/systemd"
  fi
  local unit_dest_dir="/home/signage/.config/systemd/user"

  _info "Deploying systemd unit files (URL=${api_url}, UID=${signage_uid})..."
  for unit in labwc.service signage-sidecar.service signage-player.service; do
    local src="${unit_src_dir}/${unit}"
    [ -f "${src}" ] || { _error "Unit template not found: ${src}"; exit 3; }
    sed \
      -e "s|__SIGNAGE_API_URL__|${api_url}|g" \
      -e "s|__SIGNAGE_UID__|${signage_uid}|g" \
      "${src}" > "${unit_dest_dir}/${unit}"
    chmod 0644 "${unit_dest_dir}/${unit}"
    _info "  Deployed ${unit}"
  done
  chown -R signage:signage /home/signage/.config/systemd
}

setup_sidecar_venv() {
  # Signature: setup_sidecar_venv()
  # Creates /opt/signage/pi-sidecar/.venv/ and installs requirements.
  # Pre-compiles bytecode for ProtectSystem=strict compatibility.
  local sidecar_dir="/opt/signage/pi-sidecar"
  local venv_dir="${sidecar_dir}/.venv"
  local requirements="${sidecar_dir}/requirements.txt"

  _info "Setting up sidecar Python venv..."
  [ -d "${venv_dir}" ] || python3 -m venv "${venv_dir}"

  if [ -f "${requirements}" ]; then
    "${venv_dir}/bin/pip" install --no-cache-dir -r "${requirements}"
  else
    _warn "requirements.txt not found at ${requirements}; installing locked defaults."
    "${venv_dir}/bin/pip" install --no-cache-dir \
      fastapi==0.115.12 uvicorn==0.34.0 httpx==0.28.1
  fi

  _info "Pre-compiling venv bytecode..."
  "${venv_dir}/bin/python" -m compileall "${venv_dir}/lib" -q 2>/dev/null || true

  chown -R signage:signage "${venv_dir}"
  _info "Sidecar venv ready."
}

enable_linger_signage() {
  # Signature: enable_linger_signage()
  # In chroot: creates /var/lib/systemd/linger/signage (direct file, no loginctl).
  # In runtime: calls loginctl enable-linger signage.
  if [ "${SIGNAGE_BUILD_CONTEXT:-}" = "chroot" ]; then
    _info "Enabling linger via /var/lib/systemd/linger/signage (chroot mode)..."
    mkdir -p /var/lib/systemd/linger
    touch /var/lib/systemd/linger/signage
  else
    _info "Enabling linger via loginctl..."
    loginctl enable-linger signage
  fi
}

force_wayland_if_pi3() {
  # Signature: force_wayland_if_pi3()
  # RUNTIME ONLY. Reads /proc/device-tree/model. No-op in chroot.
  if [ "${SIGNAGE_BUILD_CONTEXT:-}" = "chroot" ]; then
    return 0
  fi
  local pi_model
  pi_model=$(cat /proc/device-tree/model 2>/dev/null | tr '\0' '\n' | head -1 || echo "unknown")
  if echo "${pi_model}" | grep -q "Raspberry Pi 3"; then
    _info "Pi 3B detected — forcing Wayland via raspi-config..."
    raspi-config nonint do_wayland W2 2>/dev/null || \
      _warn "raspi-config do_wayland W2 failed (best-effort)."
  fi
}
