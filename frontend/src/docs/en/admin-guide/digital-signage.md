# Digital Signage

## Overview

Digital Signage turns any Raspberry Pi with an HDMI display into a managed kiosk that plays a loop of media items — images, videos, PDFs, converted PPTX presentations, live URLs, or HTML snippets. The KPI Dashboard acts as the control plane: admins upload media, build playlists, and assign them to devices using tags. Each Pi runs a lightweight sidecar that caches the last-known playlist and media files locally, so playback continues uninterrupted even during Wi-Fi outages.

**Supported media formats:**

| Format | Details |
|--------|---------|
| Image | JPEG, PNG, GIF, WEBP |
| Video | MP4, WEBM |
| PDF | Rendered as a slide sequence |
| PPTX | Server-side conversion to slide images — see [PPTX Best Practices](#pptx-best-practices) |
| URL | Live web page shown in a full-screen frame |
| HTML | Inline HTML snippet rendered full-screen |

## Prerequisites

- **Admin role** on the KPI Dashboard. Viewers cannot access the signage management pages.
- **Raspberry Pi 4 or Pi 5** recommended (Pi 3B is supported with caveats — see the [operator runbook](../../../../../../../docs/operator-runbook.md)).
- **≥ 16 GB microSD card**, ≥ 1 GB RAM.
- **HDMI display** connected to the Pi.
- **Local network access** from the Pi to the KPI Dashboard API host. An internet connection is needed only during initial provisioning (to clone the repo and install packages).
- The KPI Dashboard API must be reachable from the Pi: `curl http://<api-host>/api/health` should return `{"status":"ok"}`.

## Onboarding a Pi

### Step 1: Flash Raspberry Pi OS Bookworm Lite 64-bit

1. Download **Raspberry Pi Imager** from [raspberrypi.com/software](https://www.raspberrypi.com/software/).
2. Choose **Raspberry Pi OS Lite (64-bit)** — Bookworm release.
3. Open **OS Customisation** (the gear icon) before writing:
   - Set a hostname (e.g., `signage-lobby`).
   - Enable SSH and set credentials.
   - Enter your Wi-Fi SSID and password.
4. Write the image to the microSD card and insert it into the Pi.
5. Power on the Pi and wait for it to boot (first boot takes 1–2 minutes).
6. Verify the Pi is reachable: `ssh <user>@<pi-hostname>`.

### Step 2: Run the Provision Script

SSH into the Pi, then run:

```bash
# Clone the repo
sudo git clone https://github.com/<org>/kpi-dashboard /opt/signage

# Provision (replace with your API host)
sudo SIGNAGE_API_URL=<api-host:port> /opt/signage/scripts/provision-pi.sh
```

The script installs all required packages, creates the `signage` user, sets up the offline-cache sidecar, and enables the kiosk service. It exits with code 0 on success.

After the script completes, **reboot** the Pi:

```bash
sudo reboot
```

For full script documentation, including exit codes and idempotency guarantees, see `scripts/README-pi.md` in the repo.

> **Tip:** The provision script is idempotent. You can safely re-run it after a configuration change (e.g., new API host) and it will update the running services.

### Step 3: Claim the Device

Once the Pi reboots, the kiosk displays a **6-digit pairing code** on screen within 30 seconds.

1. In the KPI Dashboard, navigate to **Signage → Pair Device** (or `/signage/pair`).
2. Enter the 6-digit code.
3. Give the device a name (e.g., "Lobby Screen").
4. Assign one or more **tags** to the device (e.g., `lobby`, `floor-1`).
5. Click **Claim**.

The kiosk will begin playing content within a few seconds.

### Step 4: Assign a Playlist via Tags

Playlists are matched to devices by **tags**. A playlist plays on a device when at least one tag on the device matches a tag on the playlist.

1. Create or edit a playlist in **Signage → Playlists**.
2. Add target tags to the playlist (e.g., `lobby`).
3. Any claimed device with a matching tag will immediately pick up the playlist.

## Uploading Media

Navigate to **Signage → Media** to manage media assets. The page has two halves separated by a horizontal rule: the upper half holds the intake controls (drop zone on the left, an inline form for registering a URL or HTML snippet on the right), and the lower half lists the media you have already added.

### Uploading Images and Videos

Drag and drop files onto the left drop zone, or click **Browse files**. Supported formats: JPEG, PNG, GIF, WEBP (images), MP4, WEBM (videos).

Files are stored on the server. After upload, the asset becomes available for use in any playlist.

### Registering a URL or HTML

In the inline form to the right of the drop zone:

1. Pick the **URL** or **HTML** radio.
2. Enter a **Title** and the **Content** (a URL for "URL", an HTML snippet for "HTML").
3. Click **Register URL** (or **Register HTML**).

For URLs the kiosk loads the address in a full-screen frame; the page must be reachable from the Pi's network. For HTML the snippet is rendered full-screen — useful for custom status pages or styled text overlays.

### Uploading a PPTX Presentation

1. Click **Upload File** and select a `.pptx` file.
2. The server converts the presentation to a sequence of slide images. Monitor the **conversion status**:
   - **Pending** — queued, waiting for a conversion slot.
   - **Processing** — conversion in progress.
   - **Done** — slides are ready; the asset can be added to playlists.
   - **Failed** — conversion error. Download the file and verify it opens in PowerPoint or LibreOffice Impress without errors.
3. Once done, the asset is available as a series of slide images in the playlist builder.

See [PPTX Best Practices](#pptx-best-practices) for guidance on preparing presentations.

## Building Playlists

Navigate to **Signage → Playlists** and click **New Playlist** or open an existing one.

### Adding Items

Click **Add Item** and select a media asset from the library. You can add multiple items in sequence.

### Reordering

Drag items to reorder them. The kiosk plays items in the order shown.

### Per-Item Settings

| Setting | Description |
|---------|-------------|
| Duration | How long the item is displayed (in seconds). Videos play for their natural duration unless overridden. |
| Transition | Visual transition between items (fade, cut, etc.). |

### Tag Targeting

Assign **target tags** to the playlist. Devices with at least one matching tag will receive this playlist. A device can only play one playlist at a time — if multiple playlists match, the one with the most matching tags wins.

### Publishing

Changes take effect on the kiosk within **30 seconds** of saving (via the sidecar's polling interval).

## Offline Behavior

Each Pi runs a local **signage sidecar** that caches the playlist and all media files. If the Pi loses its Wi-Fi or network connection:

- The kiosk **continues playing** the last-known playlist in a loop.
- All media is served from the local cache at `/var/lib/signage/`.
- The offline indicator (`Offline` chip) appears in the kiosk UI.
- The sidecar is designed to handle at least **5 minutes** of continuous offline playback with no degradation.

When connectivity is restored:

- The sidecar reconnects to the backend within **30 seconds**.
- Any playlist changes made during the outage are applied automatically.

> **Note:** Media files added to the playlist after the last sync will not be available offline until the sidecar has had a chance to download them. New media items are pre-fetched in the background as soon as connectivity is restored.

## Troubleshooting

### Wi-Fi Connectivity

If the kiosk goes offline unexpectedly:

1. SSH into the Pi and check the network status:
   ```bash
   nmcli device status
   nmcli connection show --active
   ```
2. If Wi-Fi is disconnected, reconnect:
   ```bash
   nmcli device connect wlan0
   ```
3. Verify the API host is reachable from the Pi:
   ```bash
   curl http://<api-host>/api/health
   ```
4. Check the sidecar health endpoint:
   ```bash
   curl http://localhost:8080/health
   ```
   Expected when online: `{"ready": true, "online": true, "cached_items": N}`

### Pairing Code Not Appearing

If no pairing code is visible on screen after rebooting:

1. Check that the provision script completed successfully (exit code 0).
2. Check the kiosk service logs:
   ```bash
   sudo -u signage journalctl --user -u signage-player -n 50
   ```
3. Verify the API host is reachable and the `/player/` path is accessible:
   ```bash
   curl http://<api-host>/player/
   ```
4. Check the sidecar is running:
   ```bash
   sudo -u signage journalctl --user -u signage-sidecar -n 20
   ```

For step-by-step recovery procedures, see the [operator runbook](../../../../../../../docs/operator-runbook.md).

### Black Screen / No Content

A black screen after pairing usually means the device has no matching playlist:

1. Verify the device has at least one tag assigned (in **Signage → Devices**).
2. Verify a playlist exists with a matching tag and is enabled.
3. Check the sidecar:
   ```bash
   curl http://localhost:8080/health
   ```
   If `cached_items` is 0, the playlist has not yet been received. Wait 30 seconds and try again.

### PPTX Rendering Issues

If a PPTX asset shows "Failed" status or slides look wrong:

- Open the file in **PowerPoint** or **LibreOffice Impress** and verify it renders correctly locally.
- Check the conversion logs in the admin UI for the specific error.
- See [PPTX Best Practices](#pptx-best-practices) for common pitfalls.

## PPTX Best Practices

PPTX files are converted on the server using LibreOffice. To ensure reliable conversion:

**Do:**
- **Embed all fonts** before uploading. In PowerPoint: File → Options → Save → check "Embed fonts in the file". In LibreOffice: Tools → Options → LibreOffice Writer → Fonts → check "Embed fonts in the document".
- Use standard fonts (Calibri, Cambria, Arial, Times New Roman). The server has Carlito (Calibri-compatible) and Caladea (Cambria-compatible) installed.
- Keep slide layouts simple — solid backgrounds and standard shapes render most reliably.
- Save as `.pptx` (not `.ppt` or `.odp`).

**Avoid:**
- **OLE objects** (embedded spreadsheets, charts linked to Excel files) — these are not rendered by LibreOffice in server mode.
- **Embedded videos** inside the PPTX — the server extracts slides as static images; embedded video is lost. Upload the video as a separate media item.
- **External links** (hyperlinks, linked images) — the server has no internet access during conversion.
- **Non-standard or custom fonts** that are not embedded — text will fall back to a substitute font and layouts may shift.
- **Animations and transitions** — these are ignored during slide-image conversion.

> **Best approach:** Convert the presentation to PDF in PowerPoint first, then check that the PDF looks correct. If the PDF looks right, the PPTX conversion on the server will produce similar results.

## Related Articles

- [System Setup](/docs/admin-guide/system-setup) — Docker Compose overview
- [Architecture](/docs/admin-guide/architecture) — system architecture overview
- [Operator Runbook](/docs/operator-runbook) — Pi-level technical reference (systemd units, journalctl, recovery procedures)

## Schedules

Schedules play specific playlists at specific times and days. Use them when a device should show one playlist during the workday and another in the evening - for example, a menu board that switches from breakfast to lunch. When no schedule matches the current time, the device falls back to the always-on tag-based playlist.

### Fields

| Field | Description | Required | Notes |
|-------|-------------|----------|-------|
| Playlist | Which playlist this schedule plays. | Yes | Pick from existing playlists. Create one in the Playlists tab first. |
| Days | Weekdays on which this schedule is active. | Yes (>=1) | Weekdays, Weekend, and Daily quick-picks overwrite the checkbox row. |
| Start time | When the schedule activates (inclusive). | Yes | Format HH:MM. |
| End time | When the schedule deactivates (exclusive). | Yes | Format HH:MM. Must be strictly after start. |
| Priority | Tie-breaker when two schedules overlap. | No (default 0) | Higher wins. Last-updated wins on a tie. |
| Enabled | Whether the schedule is active. | No (default on) | Toggle inline in the list without opening the editor. |

### Invariants

- Start time must be strictly before end time. 11:00 to 11:00 is rejected.
- Midnight-spanning windows (e.g. 22:00 to 02:00) are not supported in a single schedule. Split them into two rows.
- The weekday bit order (Monday = bit 0 ... Sunday = bit 6) is an implementation detail. The editor shows a plain Mo-Su checkbox row.

### Worked example

1. Create Schedule A: Mon-Fri, 07:00 to 11:00, Playlist X, priority 10, enabled.
2. Create Schedule B: every day (Mon-Sun), 11:00 to 14:00, Playlist Y, priority 5, enabled.
3. At 08:30 on a Wednesday the device plays Playlist X - Schedule A matches.
4. At 12:00 on a Wednesday the device plays Playlist Y - Schedule B matches; A does not because 11:00 is exclusive.
5. At 15:00 on a Wednesday no schedule matches - the device falls back to the always-on tag-based playlist.

### Deleting a playlist referenced by a schedule

A playlist cannot be deleted while any schedule still references it. The deletion returns an error toast listing the blocking schedules; click "Schedules" in the toast to jump to the Schedules tab with those rows highlighted. Remove or reassign them there, then retry the playlist delete.

## Analytics

The Devices tab shows two badges per row computed from the device's heartbeats in the last 24 hours.

- **Uptime 24h** - percentage of one-minute windows in the last 24 hours that recorded at least one heartbeat.
- **Missed 24h** - count of one-minute windows in the last 24 hours without a heartbeat.

### Colour scale

- Green - Uptime >= 95 %. Device is healthy.
- Amber - Uptime 80 % - 95 %. Intermittent dropouts; worth checking the device's network.
- Red - Uptime < 80 %. Sustained outage; inspect power and network.
- Neutral (-) - No heartbeats recorded yet (freshly provisioned or never connected).

### How it's computed

Every successful heartbeat is logged in an append-only table. Once per minute, a sweeper drops heartbeat rows older than 25 hours. The Uptime badge counts distinct one-minute windows with at least one heartbeat and divides by the denominator.

For a freshly-provisioned new device that has only been online for e.g. 30 minutes, the denominator is 30 (not 1440) so Uptime shows an honest signal from day one. Hover the badge to see the literal numerator/denominator and the window length.

### Refresh

The table polls every 30 seconds and refreshes automatically when you switch back to the browser tab.
