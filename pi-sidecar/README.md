# Pi Sidecar

Runs on the Raspberry Pi at 127.0.0.1:8080 to proxy-cache the KPI
Dashboard signage player endpoints.

The sidecar is the offline-resilience layer for the signage kiosk. It:
- Proxies `/api/signage/player/playlist` with ETag-aware caching
- Serves `/media/<id>` from the local cache when offline
- Accepts the device JWT via `POST /token` from the player browser
- Runs a background heartbeat to the backend every 60 seconds
- Probes backend connectivity every 10 seconds; reports `online` status on `/health`

## Routes

| Route | Description |
|-------|-------------|
| `GET /health` | Always 200. Returns `{ready, online, cached_items}` |
| `POST /token` | Accepts `{"token": "<jwt>"}`, persists to `SIGNAGE_CACHE_DIR/device_token` (mode 0600), returns `{"accepted": true}` |
| `GET /api/signage/player/playlist` | ETag-aware playlist proxy; caches to disk; serves from cache when offline |
| `GET /media/<media_id>` | Serves cached media file or proxies from backend and persists |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SIGNAGE_API_BASE` | *(required)* | Backend base URL, e.g. `http://192.168.1.100:8000` |
| `SIGNAGE_CACHE_DIR` | `/var/lib/signage` | On-disk cache directory (must be writable by the `signage` user) |

## On-Disk Layout

```
/var/lib/signage/          mode 0700, owner signage:signage
├── device_token           mode 0600 — raw JWT string
├── playlist.json          mode 0600 — last known PlaylistEnvelope JSON
├── playlist.etag          mode 0600 — last known ETag string (no quotes)
└── media/                 mode 0700
    ├── <uuid1>            mode 0600 — raw bytes of media file
    └── ...
```

## Security

- Bound to `127.0.0.1:8080` only — never exposed on the LAN.
- Token file written with `os.chmod(path, 0o600)` — not readable by other users.
- Runs as the `signage` user with systemd hardening (`PrivateTmp=yes`,
  `NoNewPrivileges=yes`, `ProtectSystem=strict`, `ReadWritePaths=/var/lib/signage`).

## Dev / Local Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

SIGNAGE_API_BASE=http://localhost:8000 SIGNAGE_CACHE_DIR=/tmp/signage-cache \
  .venv/bin/uvicorn sidecar:app --host 127.0.0.1 --port 8080
```

## Test (Hardware-Free)

```bash
.venv/bin/pip install pytest respx
.venv/bin/pytest tests/ -v
```

All tests run without Pi hardware. The upstream backend is mocked via `respx`.

## Production (Pi) Startup

The sidecar is managed by a systemd user service `signage-sidecar.service`:

```ini
[Unit]
Description=KPI Signage Sidecar
Before=signage-player.service
After=network-online.target

[Service]
Type=simple
Environment=SIGNAGE_API_BASE=http://<backend-ip>:8000
Environment=SIGNAGE_CACHE_DIR=/var/lib/signage
Environment=WAYLAND_DISPLAY=wayland-1
ExecStart=/opt/signage/sidecar/.venv/bin/uvicorn sidecar:app --host 127.0.0.1 --port 8080 --app-dir /opt/signage/sidecar
PrivateTmp=yes
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=/var/lib/signage
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```
