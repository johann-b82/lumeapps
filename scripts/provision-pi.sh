#!/usr/bin/env bash
# Phase 48 D-3 / Phase 49 refactor: idempotent Pi bootstrap.
# Run as root on a fresh Bookworm Lite 64-bit image.
# Usage: sudo SIGNAGE_API_URL=http://host:port ./scripts/provision-pi.sh
#    or: sudo ./scripts/provision-pi.sh <full-api-url>
# SIGNAGE_API_URL must be a full URL including scheme, e.g. http://192.168.1.104:8000
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---------------------------------------------------------------------------
# Source the shared installer library (7 shared functions)
# ---------------------------------------------------------------------------
# shellcheck source=scripts/lib/signage-install.sh
source "${SCRIPT_DIR}/lib/signage-install.sh"

# ---------------------------------------------------------------------------
# Helpers (runtime-only; not shared with chroot path)
# ---------------------------------------------------------------------------
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'

info()  { echo -e "${GREEN}[provision-pi]${NC} $*"; }
warn()  { echo -e "${YELLOW}[provision-pi] WARN:${NC} $*"; }
error() { echo -e "${RED}[provision-pi] ERROR:${NC} $*" >&2; }

# ---------------------------------------------------------------------------
# preflight_checks — runtime-only; not shared (systemd, arch, apt checks)
# ---------------------------------------------------------------------------
preflight_checks() {
  info "=== Phase 48/49 Pi Provisioning Bootstrap ==="

  # Root check
  if [ "$(id -u)" != "0" ]; then
    error "This script must be run as root (sudo)."
    exit 1
  fi

  # Architecture check
  ARCH="$(uname -m)"
  if [ "${ARCH}" != "aarch64" ]; then
    warn "Architecture is '${ARCH}', expected 'aarch64' (64-bit ARM)."
    warn "Bookworm Lite 64-bit is the only officially supported image."
    warn "Continuing anyway — set SIGNAGE_SKIP_ARCH_CHECK=1 to silence this."
  fi

  # apt check
  if ! command -v apt-get >/dev/null 2>&1; then
    error "apt-get not found — this script requires Debian/Raspberry Pi OS."
    exit 1
  fi

  # SIGNAGE_API_URL: accept as env var OR positional arg
  if [ "${1:-}" != "" ]; then
    SIGNAGE_API_URL="${1}"
  fi
  if [ -z "${SIGNAGE_API_URL:-}" ]; then
    error "SIGNAGE_API_URL is required."
    echo ""
    echo "Usage:"
    echo "  sudo SIGNAGE_API_URL=<full-api-url> ${BASH_SOURCE[0]}"
    echo "  sudo ${BASH_SOURCE[0]} <full-api-url>"
    echo ""
    echo "SIGNAGE_API_URL must be a full URL including scheme (and port if non-default):"
    echo "  sudo SIGNAGE_API_URL=http://192.168.1.104:8000 ${BASH_SOURCE[0]}"
    exit 1
  fi

  # Print banner for operator confirmation
  echo ""
  echo "  SIGNAGE_API_URL = ${SIGNAGE_API_URL}"
  echo "  Kiosk URL       = ${SIGNAGE_API_URL}/player/"
  echo "  Repo root       = ${REPO_ROOT}"
  echo ""

  # systemd version check (Pitfall 7: loginctl enable-linger requires systemd 219+)
  SYSTEMD_VER=$(systemctl --version | head -1 | awk '{print $2}')
  if [ "${SYSTEMD_VER}" -lt 219 ] 2>/dev/null; then
    error "systemd version ${SYSTEMD_VER} is too old; loginctl enable-linger requires 219+."
    exit 1
  fi
  info "systemd ${SYSTEMD_VER} — linger support confirmed."

  # RPi archive check (Pitfall 2): chromium-browser comes from archive.raspberrypi.com
  info "Step 0.5: Checking Raspberry Pi archive configuration..."
  if [ ! -f /etc/apt/sources.list.d/raspi.list ]; then
    error "/etc/apt/sources.list.d/raspi.list is missing."
    error "chromium-browser is only available from the Raspberry Pi archive:"
    error "  https://archive.raspberrypi.com/debian/"
    error "This script must be run on a genuine Raspberry Pi OS Bookworm image."
    error "Stock Debian does not include this repository."
    exit 2
  fi
  info "raspi.list found — RPi archive configured."
}

# ---------------------------------------------------------------------------
# setup_repo_at_opt_signage — runtime-only; build-time path uses pi-gen prerun.sh
# ---------------------------------------------------------------------------
setup_repo_at_opt_signage() {
  info "Setting up repo at /opt/signage..."
  if [ -d /opt/signage/.git ]; then
    info "Repo already present — pulling latest changes."
    git -C /opt/signage pull --ff-only || {
      warn "git pull failed (detached HEAD or dirty tree). Continuing with current code."
    }
  elif [ "${REPO_ROOT}" = "/opt/signage" ]; then
    info "Already running from /opt/signage — no clone needed."
  else
    ORIGIN_URL=$(git -C "${REPO_ROOT}" config --get remote.origin.url 2>/dev/null || echo "")
    if [ -n "${ORIGIN_URL}" ]; then
      info "Cloning repo from ${ORIGIN_URL} to /opt/signage..."
      git clone "${ORIGIN_URL}" /opt/signage || {
        error "git clone failed. Clone manually: git clone ${ORIGIN_URL} /opt/signage"
        exit 3
      }
    else
      warn "No remote origin found. Copying repo from ${REPO_ROOT} to /opt/signage..."
      rsync -a --exclude='.git' "${REPO_ROOT}/" /opt/signage/ 2>/dev/null || \
        cp -r "${REPO_ROOT}/." /opt/signage/ || {
          error "Could not populate /opt/signage. Clone manually and re-run."
          exit 3
        }
    fi
  fi
  chown -R signage:signage /opt/signage
  info "Repo ready at /opt/signage."
}

# ---------------------------------------------------------------------------
# enable_and_start_services — runtime-only; no systemd running in chroot
# ---------------------------------------------------------------------------
enable_and_start_services() {
  local signage_uid="${1}"
  local xdg_runtime_dir="/run/user/${signage_uid}"

  info "Enabling and starting systemd user services..."

  # On a freshly-provisioned host, `loginctl enable-linger` alone does not
  # spawn user@UID.service before the next boot — which means the user-scope
  # dbus/systemd socket under /run/user/<UID>/ does not yet exist, so
  # `systemctl --user` fails with "Failed to connect to user scope bus via
  # local transport: No such file or directory". Start the user manager
  # explicitly so the socket is materialised, then wait a beat for dbus.
  info "  Starting user@${signage_uid}.service (materialises user-scope bus)..."
  systemctl start "user@${signage_uid}.service"

  # Wait up to 10s for /run/user/<UID>/bus to appear.
  for _ in $(seq 1 20); do
    if [ -S "${xdg_runtime_dir}/bus" ]; then
      break
    fi
    sleep 0.5
  done

  if [ ! -S "${xdg_runtime_dir}/bus" ]; then
    warn "User-scope bus socket still missing at ${xdg_runtime_dir}/bus"
    warn "Attempting systemctl --user anyway; may fail until reboot."
  fi

  sudo -u signage XDG_RUNTIME_DIR="${xdg_runtime_dir}" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=${xdg_runtime_dir}/bus" \
    systemctl --user daemon-reload || {
      warn "daemon-reload failed; services will still be enabled on next boot."
    }

  sudo -u signage XDG_RUNTIME_DIR="${xdg_runtime_dir}" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=${xdg_runtime_dir}/bus" \
    systemctl --user enable --now labwc.service signage-sidecar.service signage-player.service || {
      warn "systemctl enable --now returned non-zero (labwc may need a reboot to start)."
      warn "Services are enabled — they will start on next boot."
    }
  info "Services enabled."
}

# ---------------------------------------------------------------------------
# print_completion_banner — runtime-only
# ---------------------------------------------------------------------------
print_completion_banner() {
  local api_url="${1}"
  echo ""
  echo "========================================"
  echo "=== Provisioning complete ==="
  echo "========================================"
  echo ""
  echo "  Kiosk URL:    ${api_url}/player/"
  echo "  Pairing URL:  ${api_url}/signage/pair"
  echo ""
  echo "  Pairing code should appear on screen within 30s of first boot."
  echo "  Use the admin UI at http://${api_url}/signage/pair to claim this device."
  echo ""
  echo "  Logs:"
  echo "    sudo -u signage journalctl --user -u signage-player -f"
  echo "    sudo -u signage journalctl --user -u signage-sidecar -f"
  echo "    sudo -u signage journalctl --user -u labwc -f"
  echo ""
  echo "  Sidecar health: curl http://localhost:8080/health"
  echo ""
  echo "  If kiosk does not appear after 30s, reboot: sudo reboot"
  echo "========================================"
}

# ---------------------------------------------------------------------------
# Main — thin orchestrator calling shared library + runtime-only functions
# ---------------------------------------------------------------------------
preflight_checks "${@}"

install_signage_packages
create_signage_user
create_signage_directories

# Runtime path: clone/update repo (build-time path uses pi-gen prerun.sh)
setup_repo_at_opt_signage

setup_sidecar_venv

SIGNAGE_UID=$(id -u signage)
deploy_systemd_units "${SIGNAGE_API_URL}" "${SIGNAGE_UID}"

# Auto-detects runtime context (no SIGNAGE_BUILD_CONTEXT set) → calls loginctl
enable_linger_signage

enable_and_start_services "${SIGNAGE_UID}"

force_wayland_if_pi3

print_completion_banner "${SIGNAGE_API_URL}"
