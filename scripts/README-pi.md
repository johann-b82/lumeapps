# KPI Dashboard — Raspberry Pi Kiosk Provisioning

Quick-start guide for operators setting up a new Pi signage kiosk.
For the full technical reference, see **[docs/operator-runbook.md](../docs/operator-runbook.md)** (Plan 48-04).

---

## Prerequisites

- Raspberry Pi 4 or Pi 5 recommended (Pi 3B supported — see caveats below).
- **Raspberry Pi OS Bookworm Lite 64-bit** flashed onto a microSD card.
- Wi-Fi SSID + password configured via Raspberry Pi Imager's "OS Customisation" (pre-configure before flashing).
- SSH enabled via Raspberry Pi Imager.
- The KPI Dashboard API host reachable from the Pi's network (verify with `curl http://<api-host>/api/health`).

---

## Quickstart

```bash
# 1. SSH into the Pi
ssh <user>@<pi-host>

# 2. Clone the repo into /opt/signage (run as root or with sudo)
sudo git clone https://github.com/<org>/kpi-dashboard /opt/signage

# 3. Run the provisioning script
sudo SIGNAGE_API_URL=<api-host:port> /opt/signage/scripts/provision-pi.sh
```

**Example:**
```bash
sudo SIGNAGE_API_URL=192.168.1.100:80 /opt/signage/scripts/provision-pi.sh
```

The `SIGNAGE_API_URL` can also be passed as a positional argument:
```bash
sudo /opt/signage/scripts/provision-pi.sh 192.168.1.100:80
```

After the script exits, **reboot** so that labwc starts cleanly:
```bash
sudo reboot
```

The pairing code should appear on the HDMI display within 30 seconds of boot.

---

## What It Does

The script runs these steps in order:

| Step | Action |
|------|--------|
| 0    | Pre-flight checks: root, architecture (aarch64), apt availability, `SIGNAGE_API_URL` presence, systemd version |
| 0.5  | Verify `/etc/apt/sources.list.d/raspi.list` exists — errors if missing (required for `chromium-browser` from RPi archive) |
| 1    | `apt-get install` of all required packages: `chromium-browser`, `unclutter-xfixes`, `labwc`, `seatd`, PPTX-render fonts (Carlito/Caladea/Noto/DejaVu), `python3-venv`, `git`, `ca-certificates`, `curl`, `network-manager` |
| 2    | Create `signage` user (non-root) with groups `video,audio,render,input`; idempotent if user exists |
| 3    | Create `/var/lib/signage/` (cache dir, mode 0700) and `/opt/signage/` layout |
| 4    | Clone or pull the KPI Dashboard repo into `/opt/signage` |
| 5    | Set up Python venv at `/opt/signage/pi-sidecar/.venv`, install from `pi-sidecar/requirements.txt` |
| 5.5  | Pre-compile venv bytecode (`python -m compileall`) — required because `ProtectSystem=strict` makes `/opt` read-only at runtime |
| 6    | Write three systemd user unit files to `/home/signage/.config/systemd/user/`, substituting `SIGNAGE_API_URL` and signage user UID |
| 7    | `loginctl enable-linger signage` so user services start at boot without a login session |
| 8    | `systemctl --user daemon-reload` + `systemctl --user enable --now` for `labwc`, `signage-sidecar`, `signage-player` |
| 9    | If Pi 3B detected, force Wayland compositor via `raspi-config nonint do_wayland W2` (best-effort) |
| 10   | Print completion banner with kiosk URL, pairing URL, and log commands |

---

## Verifying the Installation

```bash
# Check sidecar health
curl http://localhost:8080/health
# Expected: {"ready": true, "online": false, "cached_items": 0}  (before pairing)

# Check service logs
sudo -u signage journalctl --user -u signage-player -f
sudo -u signage journalctl --user -u signage-sidecar -f
sudo -u signage journalctl --user -u labwc -f

# Check service status
sudo -u signage XDG_RUNTIME_DIR=/run/user/$(id -u signage) \
  systemctl --user status labwc signage-sidecar signage-player
```

**Pairing:** Once the pairing code is visible on the display, open
`http://<api-host>/signage/pair` in an admin browser, enter the 6-digit code,
assign a device name and tags. The kiosk will begin playing the matched playlist
within a few seconds of claiming.

---

## Re-Running (Idempotency)

The script is safe to re-run on an already-provisioned Pi. Each step checks
whether work has already been done before proceeding:

- User creation is guarded by `id signage` check.
- `apt-get install` is inherently idempotent.
- Directories created with `install -d` are no-ops if they already exist.
- Systemd unit files are always overwritten — this is intentional so a config
  change (e.g., new `SIGNAGE_API_URL`) takes effect on re-provision.
- `loginctl enable-linger` is a no-op if linger is already enabled.

After re-running, reload services:
```bash
sudo -u signage XDG_RUNTIME_DIR=/run/user/$(id -u signage) \
  systemctl --user daemon-reload
sudo -u signage XDG_RUNTIME_DIR=/run/user/$(id -u signage) \
  systemctl --user restart signage-sidecar signage-player
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0    | Success — provisioning complete |
| 1    | Missing required arguments or not running as root |
| 2    | `apt-get` failure — check network or package names |
| 3    | `git clone` / config failure — check remote URL or network |
| 4    | `pip install` failure — check PyPI connectivity or `requirements.txt` |

---

## Pi 3B Caveats

- Pi 3B may default to X11/LXDE on Bookworm Lite rather than Wayland/labwc.
  The provision script attempts `raspi-config nonint do_wayland W2` to force
  Wayland, but this is best-effort (LOW confidence per Phase 48 research).
- If Wayland fails to start on Pi 3B, check `journalctl --user -u labwc`.
  An X11 fallback (openbox + `DISPLAY=:0`) exists but requires a different
  set of unit files — contact the operator for the X11 variant.
- Pi 3B requires the `signage` user to be in the `render` group to avoid
  Chromium falling back to software rendering (already enforced by the script).

---

## Unit File Strategy

This plan chose **static units with token substitution** (`__SIGNAGE_API_URL__`,
`__SIGNAGE_UID__`) over systemd template units (`%i` instance specifier).

**Why:** Template units (`signage-player@api.example.com.service`) are elegant
but add complexity to the provision script and make `journalctl` queries more
verbose (`-u signage-player@api.example.com` vs `-u signage-player`). The
simpler static-unit + `sed` substitution is easier for operators to debug and
matches the project's preference for low-magic solutions.

This resolves Open Question 1 from `48-RESEARCH.md §12`.

The token `__SIGNAGE_API_URL__` in `scripts/systemd/*.service` is replaced by
`sed` during Step 6 of the provision script. The token `__SIGNAGE_UID__` is
replaced with `$(id -u signage)` at provision time (not hardcoded as `1001`),
per Pitfall 4 in the research notes.

---

## Further Reading

- **Full operator runbook:** `docs/operator-runbook.md` — systemd unit full
  content, journalctl commands, recovery procedures, factory reset, fallback
  image-only playlist (Plan 48-04).
- **User-facing admin guide:** `frontend/src/docs/en/admin-guide/digital-signage.md`
  — Pi onboarding, media upload, playlist building, offline behavior, Wi-Fi
  troubleshooting (Plan 48-04).
- **E2E results:** `.planning/phases/48-pi-provisioning-e2e-docs/48-E2E-RESULTS.md`
  — recorded timings and pass/fail for each walkthrough scenario (Plan 48-05).
- **loginctl linger:** After provision, the signage user services start at boot
  automatically. No need to `sudo -u signage systemctl --user start ...` manually
  after each reboot.
