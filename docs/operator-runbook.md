# Digital Signage Operator Runbook

**Audience:** Operators and developers who SSH into a Pi kiosk for provisioning, monitoring, and recovery.
**Admin guide (user-facing):** `frontend/src/docs/en/admin-guide/digital-signage.md`
**Quick-start:** `scripts/README-pi.md`

---

## Table of Contents

1. [Pi Hardware Requirements](#1-pi-hardware-requirements)
2. [Software Stack](#2-software-stack)
3. [Pi Image (from scratch)](#3-pi-image-from-scratch)
4. [Provision Script Reference](#4-provision-script-reference)
5. [Systemd Service Reference](#5-systemd-service-reference)
6. [Full Chromium Flag Set](#6-full-chromium-flag-set)
7. [Sidecar Cache Reference](#7-sidecar-cache-reference)
8. [signage User and Security](#8-signage-user-and-security)
9. [Recovery Procedures](#9-recovery-procedures)
10. [Fallback: Image-Only Playlist](#10-fallback-image-only-playlist)
11. [Notes on Documentation Path Amendment](#11-notes-on-documentation-path-amendment)

---

## 1. Pi Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Model | Raspberry Pi 3B (best-effort) | Raspberry Pi 4 or Pi 5 |
| RAM | 1 GB | 2 GB+ |
| Storage | 16 GB microSD | 32 GB microSD |
| Display | HDMI (any resolution) | HDMI 1080p or better |
| Network | Wi-Fi or Ethernet | Ethernet preferred for stability |

**Pi 3B caveats:**

- Pi 3B may default to X11/LXDE on Bookworm Lite rather than Wayland/labwc. The provision script attempts `raspi-config nonint do_wayland W2` to force Wayland, but this is best-effort.
- On Pi 3B, Chromium may require the `render` group for GPU acceleration. The provision script adds `signage` to `render` during `useradd`.
- If Wayland fails on Pi 3B, check `journalctl --user -u labwc`. An X11 fallback exists but requires different unit files — contact the development team for the X11 variant unit files.
- Pi 4 and Pi 5 are unambiguous targets. Wayland + labwc work without any additional steps.

---

## 2. Software Stack

| Component | Version | Package / Source |
|-----------|---------|-----------------|
| Raspberry Pi OS | Bookworm Lite 64-bit | Raspberry Pi Imager |
| Chromium | 136+ (RPi-optimised) | `chromium-browser` from RPi archive (`archive.raspberrypi.com/debian`) |
| Wayland compositor | labwc (Bookworm default since October 2024) | `labwc` |
| Seat manager | seatd | `seatd` |
| Cursor hide | unclutter-xfixes | `unclutter-xfixes` (NOT `unclutter` — does not work under Wayland) |
| Python | 3.11 (Bookworm system) | Pre-installed |
| Sidecar runtime | FastAPI 0.115.12 + uvicorn 0.34.0 + httpx 0.28.1 | venv at `/opt/signage/pi-sidecar/.venv` |
| Fonts (PPTX) | Carlito, Caladea, Noto, DejaVu | `fonts-crosextra-carlito`, `fonts-crosextra-caladea`, `fonts-noto-core`, `fonts-dejavu-core` |

**Important package notes:**

- `chromium-browser` is the RPi-optimised variant from the official Raspberry Pi repository. Standard Debian `chromium` works but lacks GPU acceleration for video. Always install `chromium-browser`. If `/etc/apt/sources.list.d/raspi.list` is missing, the provision script exits with code 2.
- `unclutter-xfixes` (not `unclutter`) — the `unclutter` package uses X11 XFixes and silently fails under labwc/Wayland.
- `seatd` is required for Wayland seat management without a display manager (gdm/lightdm are not installed on Bookworm Lite).

---

## 3. Pi Image (from scratch)

### 3.1 Download and Flash

1. Install **Raspberry Pi Imager** from [raspberrypi.com/software](https://www.raspberrypi.com/software/).
2. Insert a microSD card (≥ 16 GB).
3. In Raspberry Pi Imager:
   - **Device:** your Pi model.
   - **OS:** Raspberry Pi OS Lite (64-bit) — Bookworm release. Confirm the release name says "bookworm" before flashing.
   - **Storage:** your microSD card.
4. Click the **gear icon** (OS Customisation) before writing:
   - Set a hostname (e.g., `signage-lobby`).
   - Enable SSH and set a username/password.
   - Enter your Wi-Fi SSID and password (2.4 GHz is more reliable for Pi 3B; Pi 4/5 support 5 GHz).
5. Click **Write** and confirm the overwrite warning.

### 3.2 First Boot Verification

1. Insert the flashed microSD and power on the Pi.
2. Wait 1–2 minutes for first-boot resize and setup to complete.
3. From your laptop:
   ```bash
   ssh <user>@<pi-hostname>
   # or by IP:
   ssh <user>@<pi-ip>
   ```
4. Verify 64-bit OS:
   ```bash
   uname -m
   # Expected: aarch64
   ```
5. Verify internet access (needed for the provision script):
   ```bash
   curl -I https://github.com
   # Expected: HTTP/2 200
   ```
6. Verify API host reachability:
   ```bash
   curl http://<api-host>/api/health
   # Expected: {"status":"ok"}
   ```

---

## 4. Provision Script Reference

See `scripts/README-pi.md` for the full quickstart. This section covers technical details.

### 4.1 Invocation

```bash
# As environment variable:
sudo SIGNAGE_API_URL=<full-api-url> /opt/signage/scripts/provision-pi.sh

# As positional argument:
sudo /opt/signage/scripts/provision-pi.sh <full-api-url>
```

`SIGNAGE_API_URL` accepts a full URL including scheme and (if non-default) port. Example: `http://192.168.1.104:8000` or `https://kpi.company.internal`.

### 4.2 Exit Codes

| Code | Meaning | Common cause |
|------|---------|--------------|
| 0 | Success — provisioning complete | — |
| 1 | Missing required arguments or not running as root | Forgot `sudo` or `SIGNAGE_API_URL` (must be full URL) |
| 2 | `apt-get` failure | No internet, or `/etc/apt/sources.list.d/raspi.list` missing |
| 3 | `git clone` / config failure | No internet, or wrong repo URL |
| 4 | `pip install` failure | No internet, or PyPI connectivity |

### 4.3 Idempotency Contract

The script is safe to re-run on an already-provisioned Pi:

- `useradd` is guarded by `id signage` — skipped if user exists.
- `apt-get install` — inherently idempotent.
- `install -d` for directories — no-op if directory exists.
- Systemd unit files are **always overwritten** — this is intentional. Re-running after a config change (e.g., new `SIGNAGE_API_URL`) applies the new config.
- `loginctl enable-linger` — no-op if already enabled.

After re-running, reload services:

```bash
SIGNAGE_UID=$(id -u signage)
sudo -u signage XDG_RUNTIME_DIR=/run/user/${SIGNAGE_UID} \
  systemctl --user daemon-reload
sudo -u signage XDG_RUNTIME_DIR=/run/user/${SIGNAGE_UID} \
  systemctl --user restart signage-sidecar signage-player
```

### 4.4 Token Substitution

The provision script substitutes two tokens in the systemd unit templates before writing them:

| Token | Replaced with |
|-------|--------------|
| `__SIGNAGE_API_URL__` | Value of `SIGNAGE_API_URL` argument (full URL incl. scheme) |
| `__SIGNAGE_UID__` | Output of `id -u signage` at provision time |

**Do not hardcode UID 1001.** Different Pi images may assign a different UID to the `signage` user depending on what other users were created first.

---

## 5. Systemd Service Reference

All three services are **systemd user services** under the `signage` user. They live in `/home/signage/.config/systemd/user/` after provisioning.

`loginctl enable-linger signage` is required so the user session (and thus the user services) starts at boot without a login session.

### 5.1 labwc.service — Wayland Compositor

```ini
# ~/.config/systemd/user/labwc.service
[Unit]
Description=labwc Wayland compositor
After=default.target

[Service]
Type=simple
ExecStart=/usr/bin/labwc
Restart=on-failure
Environment=XDG_RUNTIME_DIR=/run/user/__SIGNAGE_UID__

[Install]
WantedBy=default.target
```

**Journalctl:**
```bash
sudo -u signage journalctl --user -u labwc -f
sudo -u signage journalctl --user -u labwc -n 50 --no-pager
```

**Status check:**
```bash
sudo -u signage XDG_RUNTIME_DIR=/run/user/$(id -u signage) \
  systemctl --user status labwc
```

**Common issues:**
- `Failed to start labwc` — seatd may not be running. Check `systemctl status seatd`.
- labwc starts but no Wayland socket — verify `XDG_RUNTIME_DIR` matches the actual UID: `id -u signage`.

### 5.2 signage-sidecar.service — Offline Cache Proxy

```ini
[Unit]
Description=Signage sidecar proxy cache
Documentation=https://github.com/<org>/<repo>/blob/main/docs/operator-runbook.md
After=network-online.target
Wants=network-online.target
# Sidecar must be up before the kiosk so the player can probe /health on first load.
Before=signage-player.service

[Service]
Type=simple
Restart=always
RestartSec=5

# Sidecar runs from the venv; single worker — serves exactly one device.
ExecStart=/opt/signage/pi-sidecar/.venv/bin/uvicorn sidecar:app \
    --host 127.0.0.1 \
    --port 8080 \
    --workers 1

WorkingDirectory=/opt/signage/pi-sidecar

# Hardening (D-6)
PrivateTmp=yes
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=/var/lib/signage

# Environment
Environment=SIGNAGE_API_BASE=__SIGNAGE_API_URL__
Environment=SIGNAGE_CACHE_DIR=/var/lib/signage

[Install]
WantedBy=default.target
```

**Journalctl:**
```bash
sudo -u signage journalctl --user -u signage-sidecar -f
sudo -u signage journalctl --user -u signage-sidecar -n 100 --no-pager
```

**Health check:**
```bash
curl http://localhost:8080/health
# Online: {"ready": true, "online": true, "cached_items": N}
# Offline: {"ready": true, "online": false, "cached_items": N}
# No token yet: {"ready": false, "online": false, "cached_items": 0}
```

**Common issues:**
- Sidecar starts but `online: false` — no device token yet. The kiosk must pair first and post the token via `POST http://localhost:8080/token`. This happens automatically when the player loads.
- `EROFS` errors in sidecar logs — `ProtectSystem=strict` is blocking a write outside `/var/lib/signage`. All sidecar writes should go to `/var/lib/signage/`. If the venv is writing `.pyc` files at runtime, re-run `python3 -m compileall /opt/signage/pi-sidecar` and restart the sidecar.

### 5.3 signage-player.service — Chromium Kiosk

```ini
[Unit]
Description=Signage kiosk (Chromium)
Documentation=https://github.com/<org>/<repo>/blob/main/docs/operator-runbook.md
After=graphical.target signage-sidecar.service
Requires=signage-sidecar.service

[Service]
Type=simple
Restart=always
RestartSec=5

# Wayland environment — labwc compositor must be running.
# XDG_RUNTIME_DIR is set to the signage user's runtime dir.
# Replace 1001 with the actual UID of the signage user (set by provision script).
Environment=WAYLAND_DISPLAY=wayland-1
Environment=XDG_RUNTIME_DIR=/run/user/__SIGNAGE_UID__
Environment=XDG_SESSION_TYPE=wayland

# Chromium profile dir — writable, outside ProtectSystem strictness
Environment=CHROMIUM_PROFILE_DIR=/home/signage/.config/chromium

# Guard: only start if Wayland socket exists (prevents crash-loop if labwc is not up).
ExecStartPre=/bin/bash -c 'while [ ! -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; do sleep 1; done'

ExecStart=/usr/bin/chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --autoplay-policy=no-user-gesture-required \
    --disable-session-crashed-bubble \
    --ozone-platform=wayland \
    --app=http://__SIGNAGE_API_URL__/player/ \
    --user-data-dir=${CHROMIUM_PROFILE_DIR} \
    --no-first-run \
    --disable-component-update \
    --check-for-update-interval=31536000

# Clean up crashed-session state so Chromium doesn't show recovery dialog.
ExecStartPost=/bin/bash -c 'sleep 5; find ${CHROMIUM_PROFILE_DIR}/Default -name "Crash Reports" -type d -exec rm -rf {} + 2>/dev/null || true'

# Hardening
NoNewPrivileges=yes
# Do NOT add ProtectSystem=strict — Chromium writes profile data to /home/signage.

[Install]
WantedBy=graphical-session.target
```

**Journalctl:**
```bash
sudo -u signage journalctl --user -u signage-player -f
sudo -u signage journalctl --user -u signage-player -n 100 --no-pager
```

**Status check (all three services at once):**
```bash
sudo -u signage XDG_RUNTIME_DIR=/run/user/$(id -u signage) \
  systemctl --user status labwc signage-sidecar signage-player
```

**Common issues:**
- Player keeps restarting — check if `signage-sidecar.service` is healthy first (it is `Requires=`). If the sidecar fails, the player will also fail.
- Wayland socket not found (`No such file or directory: /run/user/1001/wayland-1`) — labwc has not created the socket yet. The `ExecStartPre` guard should handle this by looping; if the loop runs indefinitely, labwc itself is not starting. Check `journalctl --user -u labwc`.
- "Session crashed" dialog on boot — `--disable-session-crashed-bubble` suppresses the bubble; `ExecStartPost` removes crash reports. If the dialog still appears, add `--disable-restore-session-state` to the `ExecStart` flags.

---

## 6. Full Chromium Flag Set

Per SGN-OPS-03 (locked, not modifiable without a requirements change):

```
/usr/bin/chromium-browser \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --autoplay-policy=no-user-gesture-required \
  --disable-session-crashed-bubble \
  --ozone-platform=wayland \
  --app=http://<api-host>/player/
```

**Flag explanations:**

| Flag | Purpose |
|------|---------|
| `--kiosk` | Full-screen mode, no browser chrome (address bar, tabs, menus) |
| `--noerrdialogs` | Suppress error dialogs that break the kiosk display |
| `--disable-infobars` | Prevent the "Chrome is being controlled by automated software" banner |
| `--autoplay-policy=no-user-gesture-required` | Allow video playlist items to autoplay without user interaction |
| `--disable-session-crashed-bubble` | Suppress the "session crashed" recovery bubble after a hard shutdown |
| `--ozone-platform=wayland` | Use the Wayland backend (required for labwc compositor on Bookworm Lite) |
| `--app=<url>` | Open the specified URL in app mode (no back/forward buttons) |

**Additional reliability flags (added by the systemd unit, not part of SGN-OPS-03):**

| Flag | Purpose |
|------|---------|
| `--no-first-run` | Skip the first-run wizard when creating a new Chromium profile |
| `--disable-component-update` | Prevent component download attempts over the network |
| `--check-for-update-interval=31536000` | Disable auto-update checks (1 year in seconds) |
| `--user-data-dir=/home/signage/.config/chromium` | Explicit profile path in a writable location |

**Wayland-specific requirements:**

The following environment variables must be set in the systemd unit:

```ini
Environment=WAYLAND_DISPLAY=wayland-1
Environment=XDG_RUNTIME_DIR=/run/user/<uid>
Environment=XDG_SESSION_TYPE=wayland
```

Replace `<uid>` with the output of `id -u signage`. The provision script does this automatically.

---

## 7. Sidecar Cache Reference

### 7.1 Directory Layout

```
/var/lib/signage/          mode 0700, owner signage:signage
├── device_token           mode 0600 — raw JWT string (no newline)
├── playlist.json          mode 0600 — last known PlaylistEnvelope JSON
├── playlist.etag          mode 0600 — last known ETag string (no quotes)
└── media/                 mode 0700
    ├── <uuid1>            mode 0600 — raw bytes of media file
    ├── <uuid2>
    └── ...
```

### 7.2 Inspection Commands

```bash
# List all cached media files (UUIDs)
ls -lh /var/lib/signage/media/

# Check how many items are cached
ls /var/lib/signage/media/ | wc -l

# View the cached playlist (pretty-printed)
python3 -m json.tool /var/lib/signage/playlist.json

# View the cached ETag
cat /var/lib/signage/playlist.etag

# Check if a device token is present (do not print it — it's a JWT)
test -f /var/lib/signage/device_token && echo "token present" || echo "no token"

# Check total cache size
du -sh /var/lib/signage/
```

### 7.3 Health Endpoint Contract

```bash
curl http://localhost:8080/health
```

Response schema:

```json
{
  "ready": true,
  "online": true,
  "cached_items": 5
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `ready` | boolean | Sidecar is running and has a valid device token |
| `online` | boolean | Backend API is reachable from the Pi |
| `cached_items` | integer | Number of media files in `/var/lib/signage/media/` |

The player's `useSidecarStatus` hook probes this endpoint every 30 seconds. When `ready: true`, `window.signageSidecarReady` is set to `true` and the player switches to sidecar-proxied media URLs (`http://localhost:8080/media/<id>`).

---

## 8. signage User and Security

### 8.1 Why Non-Root

Chromium's sandboxing requires a non-root user. Running the kiosk as root disables the sandbox, making the system vulnerable to renderer exploits. The `signage` user is a dedicated system account with only the minimum required group memberships.

### 8.2 Required Groups

```bash
usermod -aG video,audio,render,input signage
```

| Group | Required for |
|-------|-------------|
| `video` | GPU/framebuffer access for Chromium hardware acceleration |
| `audio` | Audio output for video playlist items |
| `render` | DRM render node access — required on Pi 3B for GPU access without root |
| `input` | Input device access (needed by some Wayland compositor paths) |

Missing the `render` group causes Chromium to fall back to software rendering, with a console warning and high CPU usage during video playback.

### 8.3 Systemd Service Hardening

The sidecar service (`signage-sidecar.service`) uses these hardening options:

| Option | Effect |
|--------|--------|
| `PrivateTmp=yes` | Private `/tmp` namespace — sidecar cannot access other processes' temp files |
| `NoNewPrivileges=yes` | Service cannot gain new privileges via `setuid`, `setgid`, or file capabilities |
| `ProtectSystem=strict` | Root filesystem is read-only; only paths in `ReadWritePaths=` are writable |
| `ReadWritePaths=/var/lib/signage` | Only the cache directory is writable at runtime |

The player service (`signage-player.service`) uses only `NoNewPrivileges=yes`. `ProtectSystem=strict` is **not** applied to the player because Chromium writes profile data to `/home/signage/.config/chromium`.

### 8.4 Cache Directory Permissions

```bash
/var/lib/signage/          # mode 0700, owner signage:signage
/var/lib/signage/device_token  # mode 0600
/var/lib/signage/media/<id>    # mode 0600
```

The device token (JWT) must be readable only by the `signage` user. The sidecar's write path calls `os.chmod(path, 0o600)` after writing the token file.

---

## 9. Recovery Procedures

### 9.1 Restart the Kiosk

```bash
SIGNAGE_UID=$(id -u signage)
sudo -u signage XDG_RUNTIME_DIR=/run/user/${SIGNAGE_UID} \
  systemctl --user restart signage-player
```

The kiosk will reload the player page. Cached content plays immediately while the sidecar re-syncs.

### 9.2 Restart the Sidecar

```bash
SIGNAGE_UID=$(id -u signage)
sudo -u signage XDG_RUNTIME_DIR=/run/user/${SIGNAGE_UID} \
  systemctl --user restart signage-sidecar
```

After restart, the sidecar reads `/var/lib/signage/device_token` if present. The player re-posts the token automatically on the next `/health` probe (within 30 seconds). Cached media is preserved across restarts.

### 9.3 Restart the Wayland Compositor

```bash
SIGNAGE_UID=$(id -u signage)
sudo -u signage XDG_RUNTIME_DIR=/run/user/${SIGNAGE_UID} \
  systemctl --user restart labwc
```

This will briefly black-screen. The player and sidecar will restart via their `After=` dependencies.

### 9.4 Full Service Restart

```bash
SIGNAGE_UID=$(id -u signage)
sudo -u signage XDG_RUNTIME_DIR=/run/user/${SIGNAGE_UID} \
  systemctl --user restart labwc signage-sidecar signage-player
```

### 9.5 Reprovision (Config Change)

Re-run the provision script after any config change (new API host, updated packages):

```bash
sudo SIGNAGE_API_URL=<new-full-api-url> /opt/signage/scripts/provision-pi.sh
```

Then reload services:

```bash
SIGNAGE_UID=$(id -u signage)
sudo -u signage XDG_RUNTIME_DIR=/run/user/${SIGNAGE_UID} \
  systemctl --user daemon-reload
sudo -u signage XDG_RUNTIME_DIR=/run/user/${SIGNAGE_UID} \
  systemctl --user restart signage-sidecar signage-player
```

### 9.6 Factory Reset (Re-pair)

To unpair a device and pair it as new:

```bash
# 1. Remove the cache (clears device token + cached media + playlist)
sudo rm -rf /var/lib/signage/
sudo install -d -m 0700 -o signage -g signage /var/lib/signage
sudo install -d -m 0700 -o signage -g signage /var/lib/signage/media

# 2. Restart the sidecar (it will start without a token)
SIGNAGE_UID=$(id -u signage)
sudo -u signage XDG_RUNTIME_DIR=/run/user/${SIGNAGE_UID} \
  systemctl --user restart signage-sidecar signage-player

# 3. The kiosk will display a new 6-digit pairing code within 30 seconds.
```

After factory reset, use the admin UI (`/signage/pair`) to re-pair the device.

### 9.7 Chromium Profile Corruption Fix

After a hard power-cut, Chromium may show a "session crashed" recovery dialog or fail to start cleanly. To fix:

```bash
# Clear the Chromium profile
sudo -u signage rm -rf /home/signage/.config/chromium

# Restart the player
SIGNAGE_UID=$(id -u signage)
sudo -u signage XDG_RUNTIME_DIR=/run/user/${SIGNAGE_UID} \
  systemctl --user restart signage-player
```

Chromium will create a fresh profile on next start. The kiosk app state (device token) is stored in `/var/lib/signage/device_token`, not in the Chromium profile, so no re-pairing is required.

### 9.8 Wayland Socket Race (Pitfall 3)

**Symptom in journalctl:**
```
signage-player[XXXX]: [ERROR:ozone_platform_wayland.cc] Failed to connect to Wayland display
```

or the player enters a rapid crash-restart loop immediately after boot.

**Cause:** `graphical.target` reached before labwc created the Wayland socket at `/run/user/<uid>/wayland-1`.

**The `ExecStartPre` guard** in `signage-player.service` loops until the socket exists:
```bash
while [ ! -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; do sleep 1; done
```

If this loop runs indefinitely, the real problem is that labwc is not starting:

```bash
sudo -u signage journalctl --user -u labwc -n 30 --no-pager
# Look for: "Failed to start" or "seatd: permission denied"
```

To fix seatd permission issues:
```bash
sudo usermod -aG input,video signage
sudo systemctl restart seatd
```

Then restart labwc:
```bash
SIGNAGE_UID=$(id -u signage)
sudo -u signage XDG_RUNTIME_DIR=/run/user/${SIGNAGE_UID} \
  systemctl --user restart labwc
```

---

## 10. Fallback: Image-Only Playlist

If a specific Pi hardware configuration cannot render PPTX or PDF items (e.g., conversion succeeded but slides do not display correctly due to font rendering issues), the operator can build an **image-only fallback playlist**:

1. In the admin UI (**Signage → Media**), upload pre-rendered PNG or JPEG exports of the presentation slides.
   - In PowerPoint: File → Export → Export as PNG (one file per slide).
   - In LibreOffice Impress: File → Export → PNG.
2. Create a new playlist containing only the image items.
3. Assign the same tags as the original playlist.
4. If multiple playlists match, temporarily remove the PPTX-based playlist's tags to force the image fallback to take precedence.

This fallback is explicitly documented in SGN-OPS-03 as a supported configuration. It works on all Pi models, including Pi 3B, because images have no conversion dependency on the Pi.

---

## 11. Notes on Documentation Path Amendment

REQUIREMENTS.md SGN-OPS-01 originally referenced:

```
frontend/src/docs/admin/digital-signage.{en,de}.md
```

The actual path used follows the established in-app docs convention (same as `sensor-monitor.md`, `personio.md`, etc.):

```
frontend/src/docs/{en,de}/admin-guide/digital-signage.md
```

This is a requirements text typo, not an implementation error. The intent of SGN-OPS-01 — "bilingual admin guide covering Pi onboarding, media upload, playlist building, offline behavior, PPTX best practices" — is fully satisfied by the files at the corrected paths.

**Plan 48-05's `48-VERIFICATION.md` formalizes this amendment.** This note is here for documentation authors and future plan writers who reference the literal path in REQUIREMENTS.md.

---

## Further Reading

- `scripts/README-pi.md` — Quick-start provisioning guide
- `frontend/src/docs/en/admin-guide/digital-signage.md` — User-facing admin guide (EN)
- `frontend/src/docs/de/admin-guide/digital-signage.md` — User-facing admin guide (DE)
- `.planning/phases/48-pi-provisioning-e2e-docs/48-E2E-RESULTS.md` — E2E walkthrough results (Plan 48-05)

---

## 12. Directus Data Model — DO NOT EDIT IN UI

**Rule: Never edit the Directus Data Model using the Directus admin UI.**

Alembic is the sole DDL owner for this project. All table creation, column additions, index creation, and constraint changes happen in `backend/alembic/versions/*.py` migration files. Directus metadata (what Directus knows about the tables — represented as rows in `directus_collections`, `directus_fields`, `directus_relations`) is derived from and must stay in sync with the committed `directus/snapshots/v1.22.yaml`.

**Why this matters:** The CI drift guard (Guard B) runs `npx directus schema snapshot` against the live Directus instance and diffs the output against `directus/snapshots/v1.22.yaml`. Any edit made via the Data Model UI will produce a diff and **block PRs**. The guard treats any diff as a schema drift violation.

**How to change schema correctly:**

1. Write an Alembic migration in `backend/alembic/versions/` that modifies the database schema.
2. Regenerate `directus/snapshots/v1.22.yaml` by running:
   ```bash
   make schema-fixture-update
   ```
   This regenerates both the DDL hash fixture (`directus/fixtures/schema-hash.txt`) and the snapshot YAML.
3. Commit the Alembic migration, the updated snapshot YAML, and the updated hash fixture together in a single commit.

**Detection:** Guard B (snapshot diff) runs in CI on every PR. Guard A (DDL hash) runs in CI to detect out-of-band database changes that bypass Alembic.

---

## 13. Recovery: directus-schema-apply Fails with "Relation Already Exists" (#25760)

**Symptoms:** `docker compose logs directus-schema-apply` shows:

```
Collection already exists
```

or:

```
relation "<table_name>" already exists
```

**Cause:** Known regression in Directus 11.10+ ([issue #25760](https://github.com/directus/directus/issues/25760)). When the snapshot YAML's collection entries have a `schema:` block with a `name` field, `directus schema apply` tries to `CREATE TABLE` even though the table already exists (created by Alembic). The v1.22 snapshot uses `schema: null` on every collection to avoid this, but the issue can recur if the YAML is hand-edited.

**Happy-path verification:** The `directus-schema-apply` container should exit 0 and produce log output ending with something like `Schema applied successfully`. If it exits non-zero, check the logs.

**Fallback (operator-run — not automated):**

This fallback registers each failing collection via the Directus REST API using `schema: null` (metadata-only), which is idempotent:

1. Get an admin token:
   ```bash
   TOKEN=$(curl -sX POST http://localhost:8055/auth/login \
     -H 'Content-Type: application/json' \
     -d "{\"email\":\"$DIRECTUS_ADMIN_EMAIL\",\"password\":\"$DIRECTUS_ADMIN_PASSWORD\"}" \
     | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
   echo "Token acquired: ${TOKEN:0:20}..."
   ```

2. For each failing collection, POST metadata-only (replace `<collection_name>` and `<note>`):
   ```bash
   curl -sX POST http://localhost:8055/collections \
     -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"collection":"<collection_name>","schema":null,"meta":{"note":"<note>","hidden":false}}'
   ```

   Collections to register (if not yet registered):
   - `signage_devices`, `signage_playlists`, `signage_playlist_items`
   - `signage_device_tags`, `signage_playlist_tag_map`, `signage_device_tag_map`
   - `signage_schedules`, `sales_records`, `personio_employees`

3. Re-run the schema apply to confirm it is now a no-op:
   ```bash
   docker compose up -d directus-schema-apply
   docker compose logs directus-schema-apply
   ```
   The second run should exit 0 with no error output.

---

## 14. DB_EXCLUDE_TABLES Requires `up -d`, Not `restart`

**Rule: After changing `DB_EXCLUDE_TABLES` in `docker-compose.yml`, run `docker compose up -d directus`, not `docker compose restart directus`.**

`docker compose restart directus` restarts the container process but does NOT re-read environment variables — the container was created with the old env baked in. To pick up the new `DB_EXCLUDE_TABLES` value, Compose must recreate the container:

```bash
# Correct: recreates the directus container with the updated env
docker compose up -d directus

# WRONG: does not pick up env changes
docker compose restart directus
```

**When this matters:** Any time you shrink or expand `DB_EXCLUDE_TABLES`, run `up -d`. This is especially important after the v1.22 migration because the table set changed significantly.

---

## 15. SSE is Best-Effort — 30-Second Poll is the Durability Floor

The Postgres LISTEN/NOTIFY SSE bridge (`signage_change` channel) provides at-most-once delivery. During a database restart or a listener reconnect window (up to 30s with exponential backoff), events can be missed.

**What this means:**
- Pi players receive `playlist-changed`, `device-changed`, and `schedule-changed` SSE events within 500 ms of a Directus or FastAPI mutation under normal conditions.
- During a database restart or reconnect window, events are silently lost.
- Players compensate by polling `GET /api/signage/player/playlist` every 30 seconds. Any change missed via SSE will be caught within 30s.

**The 30s poll is the durability ceiling, not a fallback.** It always runs, regardless of SSE health.

**No event-log table, no replay.** If strict zero-loss delivery is needed, the 30s poll is the only guarantee. Missed events during reconnect are logged as WARN in `docker compose logs backend`:

```
signage_pg_listen: reconnecting attempt=N backoff=Xs err=<reason>
```

---

## 16. Rollback Recipe — Partial directus-schema-apply Failure on Fresh Volume

If `directus-schema-apply` fails mid-way on a clean volume (e.g., on first `docker compose up -d`):

**Step 1:** Inspect the logs to identify the failing collection:

```bash
docker compose logs directus-schema-apply
```

**Step 2:** If the failure is `#25760` ("relation already exists"), follow the fallback recipe in Section 13 above. The REST `POST /collections` approach is idempotent — running it multiple times for the same collection is safe.

**Step 3:** If the failure is unrelated to #25760 (e.g., a network error or a malformed YAML):

```bash
# Tear down the stack and all volumes
docker compose down -v

# Restart only the database and Directus (without the schema-apply)
docker compose up -d db directus

# Wait for directus to be healthy, then inspect logs
docker compose logs directus

# Fix the YAML or the compose config, then redeploy
docker compose up -d
```

**Step 4:** After a successful `docker compose up -d`, verify the 9 collections are registered:

```bash
TOKEN=$(curl -sX POST http://localhost:8055/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$DIRECTUS_ADMIN_EMAIL\",\"password\":\"$DIRECTUS_ADMIN_PASSWORD\"}" \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
curl -s "http://localhost:8055/collections" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | grep '"collection"' | head -20
```

You should see `signage_devices`, `signage_playlists`, `signage_playlist_items`, `signage_device_tags`, `signage_playlist_tag_map`, `signage_device_tag_map`, `signage_schedules`, `sales_records`, and `personio_employees` in the output.

---

## v1.22 Rollback Procedure

If a critical regression is discovered after a v1.22 deployment, the
following procedure restores v1.21 signage admin behavior. Total time:
~10 minutes.

**Rollback target:** the commit immediately PRECEDING Phase 68 (the first
MIG-SIGN migration phase). Older targets — pre-Phase 65 — are NOT
supported, because Phase 65 added Postgres triggers via Alembic that
would need to be reverted manually (out of scope).

**Prerequisites:** SSH access to the production host, ability to run
`docker compose` commands as the deploy user, admin Directus credentials.

### Steps

1. **Checkout pre-Phase-68 commit** on the production host:
   ```bash
   cd /opt/kpi-dashboard
   git fetch --all
   git checkout <pre-phase-68-sha>   # see CHANGELOG / git log --oneline
   ```

2. **Tear down + bring up clean:**
   ```bash
   docker compose down -v
   docker compose up -d --wait
   ```
   `down -v` drops named volumes (DB, Directus uploads). Confirm before
   running on production — restore from the latest `./backups/` if needed.

3. **Wait for healthchecks:** `docker compose ps` — all services
   must show `healthy`. Approx. 60s for first-boot Postgres seeding.

4. **Log in as Admin** at `https://<host>/login`.

5. **Verify signage admin renders v1.21 shape** (each step ≤ 30s):
   - `/signage/devices` — admin Devices tab shows the v1.21 7-column layout
     (Name, Status, Last Seen, Tags, Current Playlist, Uptime, Actions).
   - `/signage/playlists` — admin Playlists tab loads, lists existing playlists.
   - Pair one device end-to-end (`/signage/pair` → enter code on Pi → confirm
     device appears in `/signage/devices`).
   - Push one playlist update — Pi player swaps content within ~500 ms (SSE).
   - View one sales dashboard at `/sales` — KPI cards + chart render.

6. **Pass / Fail criteria:**
   - **Pass:** all 6 verifications green → v1.21 behavior restored.
   - **Fail:** open an issue with `docker compose logs --no-color > rollback.log`
     attached, and abort rollback (re-checkout main).

### Known limitations

- Phase 65 (schema + AuthZ + SSE bridge) is schema-additive — its triggers
  remain in place after a Phase 68+ rollback. They are inert when no Directus
  writes touch the trigger-bearing tables (which is the v1.21 state). No
  action required, but operators should know the triggers exist post-rollback.
- Composite-PK Directus collections (`signage_playlist_tag_map`,
  `signage_device_tag_map`) return 403 to admin REST queries on the v1.22
  forward state too — this is unrelated to rollback.
