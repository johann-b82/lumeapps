<!-- generated-by: gsd-doc-writer -->
# API Route Contract — Admin vs Viewer

**Milestone:** v1.11-directus (auth model)
**Last updated:** 2026-07-14 (added Finance, Procurement, Production, ATR, and Fair domains)
**Enforcement:** FastAPI dependency `app.security.directus_auth.require_admin` on every mutation route. See `backend/tests/test_rbac.py` for the machine-verified matrix.

## Roles

- **Admin** — full read + write access across all `/api/*` routes.
- **Viewer** — read access only. Mutation attempts return HTTP 403 with body:
  ```json
  {"detail": "admin role required"}
  ```
- **Device** — signage kiosks authenticate with a device JWT (minted at pairing, rolled on every heartbeat, revoke-only). Gate: `app.security.device_auth.get_current_device`, applied router-level on `/api/signage/player/*`.
- **Public** — unauthenticated endpoints (no JWT required): `/health`, `/docs`, `/openapi.json`, `/api/auth/forward` (Caddy `forward_auth` target — previously the authentication for the `/paperless/*`, `/pdf/*`, `/op/*` embedded apps, which were removed 2026-07-14; the endpoint is now unused but retained and allowlisted), `/api/auth/clear-cookies` (one-shot cookie flush during the v1.48 cookie-mode → session-mode migration), `/api/settings/logo/public`, `/api/hr/embed/*` (kiosk iframe, LAN-only risk acknowledged in `hr_embed.py`), `/api/worldcup/embed/today` (kiosk iframe; football-data.org key never leaves the server), `/api/signage/pair/request` + `/api/signage/pair/status` (an un-paired kiosk has no token to present), and `/player/*` (static signage player bundle). All public auth-adjacent routes are explicitly allowlisted in `backend/tests/test_admin_gate_audit.py::ADMIN_GATE_ALLOWLIST` with rationale inline.

Role is resolved from the Directus-issued JWT (HS256, shared secret). Role changes made in the Directus admin UI take effect on the user's next JWT refresh — no server-side session invalidation needed (stateless JWT).

## Reads migrated to Directus

Plain CRUD reads no longer live in FastAPI — the frontend reads them via the Directus SDK (`readItems`/`readItem`). Removed FastAPI routes:

- `GET /api/uploads` → Directus `upload_batches` collection (v1.23 C-1)
- `GET /api/data/sales` and `GET /api/data/employees` → Directus collections; the old `data.py` router was deleted (only the computed `GET /api/data/employees/overtime` survives)
- `GET/POST /api/signage/media` (list/create non-PPTX) and `GET /api/signage/media/{id}` → Directus `signage_media` (admin-only)
- Playlist `POST/GET/PATCH` and tag mapping → Directus `signage_playlists` + `signage_playlist_tag_map` (Phase 69); only the structured-409 `DELETE` survives in FastAPI
- Signage device row CRUD → Directus; only the calibration `PATCH` survives in FastAPI

FastAPI keeps only compute-justified routes (file parsing, cascade deletes, SSE fanout, upstream proxying, structured 409 bodies).

## Route Matrix

### KPIs & data (Viewer-readable)

| Method | Path                                  | Viewer | Admin | Notes |
|--------|---------------------------------------|:------:|:-----:|-------|
| GET    | /api/kpis                             |   ✓    |   ✓   | Sales KPI summary |
| GET    | /api/kpis/chart                       |   ✓    |   ✓   | Chart data |
| GET    | /api/kpis/latest-upload               |   ✓    |   ✓   | Most recent upload metadata |
| GET    | /api/hr/kpis                          |   ✓    |   ✓   | HR KPI summary |
| GET    | /api/hr/kpis/history                  |   ✓    |   ✓   | HR KPI time series |
| GET    | /api/hr/birthdays/this-week           |   ✓    |   ✓   | Active employees with birthday in current ISO week |
| GET    | /api/hr/joiners/recent                |   ✓    |   ✓   | Recent joiners (default: last 2 weeks) |
| GET    | /api/hr/employees/{employee_id}/photo |   ✓    |   ✓   | Personio profile picture proxy |
| GET    | /api/data/employees/overtime          |   ✓    |   ✓   | Computed overtime per employee (row data lives in Directus) |
| GET    | /api/data/sales/contacts-weekly       |   ✓    |   ✓   | Weekly contacts KPI |
| GET    | /api/data/sales/orders-distribution   |   ✓    |   ✓   | Orders distribution KPI |
| GET    | /api/data/sales/customer-share        |   ✓    |   ✓   | Customer share KPI |
| GET    | /api/quality/audit-findings           |   ✓    |   ✓   | Audit findings KPI value |
| GET    | /api/quality/audit-findings/list      |   ✓    |   ✓   | Audit findings listing |
| GET    | /api/quality/audit-findings/history   |   ✓    |   ✓   | Audit findings time series |
| GET    | /api/quality/complaint-rate           |   ✓    |   ✓   | Customer complaint-rate KPI value |
| GET    | /api/quality/complaint-rate/history   |   ✓    |   ✓   | Complaint-rate time series |
| GET    | /api/quality/complaints/list          |   ✓    |   ✓   | Customer complaints listing |
| GET    | /api/finance/material-cost-ratio          |   ✓    |   ✓   | Material-cost-ratio KPI value |
| GET    | /api/finance/material-cost-ratio/history  |   ✓    |   ✓   | Material-cost-ratio time series |
| GET    | /api/finance/material-cost-ratio/list     |   ✓    |   ✓   | Material-cost-ratio row listing |
| GET    | /api/finance/personnel-cost-ratio         |   ✓    |   ✓   | Personnel-cost-ratio KPI value |
| GET    | /api/finance/personnel-cost-ratio/history |   ✓    |   ✓   | Personnel-cost-ratio time series |
| GET    | /api/finance/personnel-cost-ratio/list    |   ✓    |   ✓   | Personnel-cost-ratio row listing |
| GET    | /api/procurement/otd                  |   ✓    |   ✓   | On-time-delivery (supplier) KPI value |
| GET    | /api/procurement/otd/history          |   ✓    |   ✓   | OTD time series |
| GET    | /api/procurement/otd/list             |   ✓    |   ✓   | OTD row listing |
| GET    | /api/production/verzug                 |   ✓    |   ✓   | Production delay (Verzug) KPI value |
| GET    | /api/production/verzug/history         |   ✓    |   ✓   | Verzug time series |
| GET    | /api/production/verzug/list            |   ✓    |   ✓   | Verzug per-order listing |
| GET    | /api/production/verzug/overdue         |   ✓    |   ✓   | Currently overdue orders |
| GET    | /api/settings                         |   ✓    |   ✓   | Read settings (colors, app name) |
| GET    | /api/settings/personio-options        |   ✓    |   ✓   | Live Personio metadata — read-only |
| GET    | /api/settings/logo                    |   ✓    |   ✓   | Serves raw logo bytes |
| GET    | /api/sync/meta                        |   ✓    |   ✓   | Last sync metadata |

### Uploads (Admin-only, file parsing)

All under router-level `require_admin` in `backend/app/routers/uploads.py`. Each upload writes an `upload_batches` row; `kind` discriminates.

| Method | Path                        | Viewer | Admin | Notes |
|--------|-----------------------------|:------:|:-----:|-------|
| POST   | /api/upload                 |   —    |   ✓   | Legacy 60-col ERP orders file — `kind='orders'` |
| POST   | /api/upload-contacts        |   —    |   ✓   | Kontakte (.txt) — `kind='contacts'` (v1.46) |
| POST   | /api/upload-quality         |   —    |   ✓   | Quality records — `kind='quality'` |
| POST   | /api/upload-interessenten   |   —    |   ✓   | Interessenten — `kind='interessenten'` |
| POST   | /api/upload-angebote        |   —    |   ✓   | Angebote (offers) — `kind='offers'` |
| POST   | /api/upload-umsatz          |   —    |   ✓   | AswKpf_RG.txt revenue/credit-note dump — `kind='revenues'`; idempotent upsert `ON CONFLICT (vorgang_nr)` (v1.53) |
| POST   | /api/upload-auftraege       |   —    |   ✓   | AswKpf_AUF.txt order book (18-col .txt) — `kind='auftraege'`; idempotent upsert; supersedes `POST /api/upload` as order-side KPI source (v1.54) |
| DELETE | /api/uploads/{batch_id}     |   —    |   ✓   | Cascade-deletes records of the batch |

### Settings & Personio sync (Admin mutations)

| Method | Path                | Viewer | Admin | Notes |
|--------|---------------------|:------:|:-----:|-------|
| PUT    | /api/settings       |   —    |   ✓   | Update colors / app name / credentials (incl. worldcup API key + refresh interval) |
| POST   | /api/settings/logo  |   —    |   ✓   | Logo upload (.png/.svg, max 1 MB) |
| POST   | /api/sync           |   —    |   ✓   | Full Personio sync (blocking) |
| POST   | /api/sync/test      |   —    |   ✓   | Personio credential test |

Settings PUT also carries the v1.83 Office 365 e-mail credentials (`email_tenant_id`, `email_client_id`, write-only `email_client_secret`, `email_sender_address`, `email_sender_name`, `email_enabled`).

### E-Mail (Admin-only) — v1.83 background module

Shared notification service (Office 365 / Microsoft Graph). Router-level `require_admin`. Both routes return `{ok, error}` (a failed send is HTTP 200 with `ok=false`). See [modules/email.md](modules/email.md) for the connection contract and Azure setup.

| Method | Path                             | Viewer | Admin | Notes |
|--------|----------------------------------|:------:|:-----:|-------|
| POST   | /api/email/test                  |   —    |   ✓   | Send a probe mail to one address `{to}` |
| POST   | /api/email/send                  |   —    |   ✓   | Generic send `{to[], subject, body_html, cc?, body_text?}` |
| POST   | /api/email/delegated/start       |   —    |   ✓   | Begin device-code sign-in (delegated mode) → `{device_code, user_code, verification_uri, interval, ...}` |
| POST   | /api/email/delegated/poll        |   —    |   ✓   | Poll once `{device_code}` → `{status: pending\|complete\|error, account?}` |
| POST   | /api/email/delegated/disconnect  |   —    |   ✓   | Clear the stored delegated token |

Two send modes, switchable via `email_auth_mode` on `PUT /api/settings`: `app` (client-credentials) or `delegated` (device-code sign-in with the admin's own M365 account).

### ATR — Lieferschein → ATR document (Admin-only)

Router-level `require_admin` on `/api/atr` (`atr.py`) and `/api/atr/deliveries` (`atr_delivery.py`). Parses Diehl Lieferschein PDFs, matches positions against the parts catalog, and generates the ATR xlsx/pdf + container label; an optional SMB auto-scan drives the whole flow from a network folder. `po_pos` is taken from the Lieferschein ("Auftrag Nr. \<BA\> / \<Pos\>"), not the catalog. See [modules/atr.md](modules/atr.md).

| Method | Path                                          | Viewer | Admin | Notes |
|--------|-----------------------------------------------|:------:|:-----:|-------|
| —      | /api/atr/parts[/{id}]                         |   —    |   ✓   | Parts catalog CRUD (GET/POST/PATCH/DELETE) |
| GET/PATCH | /api/atr/template                          |   —    |   ✓   | ATR header data; `POST /template/structure` uploads the structural workbook |
| POST   | /api/atr/import/preview · /commit             |   —    |   ✓   | Import reference file(s) into the catalog |
| POST   | /api/atr/deliveries/upload                    |   —    |   ✓   | Upload a Lieferschein PDF → draft delivery |
| GET    | /api/atr/deliveries/input-files               |   —    |   ✓   | List PDFs in the SMB input folder |
| POST   | /api/atr/deliveries/input-files/process       |   —    |   ✓   | Process one input file manually |
| GET    | /api/atr/deliveries · /{id}                   |   —    |   ✓   | List deliveries / detail |
| PATCH  | /api/atr/deliveries/{id} · /{id}/items/{item_id} | —   |   ✓   | Edit header / position data |
| POST   | /api/atr/deliveries/{id}/generate             |   —    |   ✓   | Build documents (and deliver, for scan origin) |
| GET    | /api/atr/deliveries/{id}/files/{kind}         |   —    |   ✓   | Download `atr_xlsx` · `atr_pdf` · `label_docx` |

The auto-scan (`_run_atr_scan` in `scheduler.py`, interval `atr_scan_interval_s`) only re-skips a filename while an **open `draft`** delivery for it still exists — once past draft, a re-appearing same-named file is processed again.

### Sensors (Admin-only, including reads)

Router-level `require_admin` on the whole `/api/sensors` router — Viewers get 403 even on GETs.

| Method | Path                              | Viewer | Admin | Notes |
|--------|-----------------------------------|:------:|:-----:|-------|
| GET    | /api/sensors                      |   —    |   ✓   | List sensors |
| POST   | /api/sensors                      |   —    |   ✓   | Create sensor (201) |
| PATCH  | /api/sensors/{sensor_id}          |   —    |   ✓   | Update sensor |
| DELETE | /api/sensors/{sensor_id}          |   —    |   ✓   | Delete sensor (204) |
| GET    | /api/sensors/{sensor_id}/readings |   —    |   ✓   | Reading history |
| GET    | /api/sensors/status               |   —    |   ✓   | Current status of all sensors |
| POST   | /api/sensors/poll-now             |   —    |   ✓   | Trigger immediate poll |
| POST   | /api/sensors/snmp-probe           |   —    |   ✓   | SNMP single-OID probe |
| POST   | /api/sensors/snmp-walk            |   —    |   ✓   | SNMP walk |

### ATR — parts & template (`/api/atr`, Admin-only)

Router-level `require_admin` on the whole `/api/atr` router (`backend/app/routers/atr.py`) — Viewers get 403 even on GETs. ATR = Abnahme-/Teile-Reporting; the parts catalog is populated via the Excel preview→commit import flow.

| Method | Path                          | Viewer | Admin | Notes |
|--------|-------------------------------|:------:|:-----:|-------|
| GET    | /api/atr/parts                |   —    |   ✓   | List parts catalog |
| GET    | /api/atr/parts/{part_id}      |   —    |   ✓   | Single part |
| POST   | /api/atr/parts                |   —    |   ✓   | Create part (201) |
| PATCH  | /api/atr/parts/{part_id}      |   —    |   ✓   | Update part |
| DELETE | /api/atr/parts/{part_id}      |   —    |   ✓   | Delete part (204) |
| GET    | /api/atr/template             |   —    |   ✓   | Read PDF/report template |
| PATCH  | /api/atr/template             |   —    |   ✓   | Update template |
| POST   | /api/atr/template/structure   |   —    |   ✓   | Update template structure |
| POST   | /api/atr/import/preview       |   —    |   ✓   | Excel import — dry-run preview |
| POST   | /api/atr/import/commit        |   —    |   ✓   | Excel import — commit rows |

### ATR — deliveries & fileserver (`/api/atr/deliveries`, `/api/atr/fileserver`, Admin-only)

Router-level `require_admin` on both (`backend/app/routers/atr_delivery.py`; fileserver router lives in `settings.py`). Delivery PDF generation = openpyxl body + LibreOffice UNO print-header.

| Method | Path                                            | Viewer | Admin | Notes |
|--------|-------------------------------------------------|:------:|:-----:|-------|
| POST   | /api/atr/deliveries/upload                      |   —    |   ✓   | Upload delivery source file (201) |
| GET    | /api/atr/deliveries/input-files                 |   —    |   ✓   | List SMB input files |
| POST   | /api/atr/deliveries/input-files/process         |   —    |   ✓   | Process an SMB input file (201) |
| GET    | /api/atr/deliveries                             |   —    |   ✓   | List deliveries |
| GET    | /api/atr/deliveries/{delivery_id}               |   —    |   ✓   | Single delivery |
| PATCH  | /api/atr/deliveries/{delivery_id}               |   —    |   ✓   | Update delivery |
| PATCH  | /api/atr/deliveries/{delivery_id}/items/{item_id} |  —   |   ✓   | Update delivery line item |
| POST   | /api/atr/deliveries/{delivery_id}/generate      |   —    |   ✓   | Generate PDF/manifest |
| GET    | /api/atr/deliveries/{delivery_id}/files/{kind}  |   —    |   ✓   | Download a generated file |
| POST   | /api/atr/fileserver/test                        |   —    |   ✓   | Test SMB fileserver connection |

### Fair — projects & balloons (`/api/fair`, Admin-only)

Router-level `require_admin` on the whole `/api/fair` router (`backend/app/routers/fair.py`).

| Method | Path                                          | Viewer | Admin | Notes |
|--------|-----------------------------------------------|:------:|:-----:|-------|
| POST   | /api/fair/projects                            |   —    |   ✓   | Create project (201) |
| GET    | /api/fair/projects                            |   —    |   ✓   | List projects |
| GET    | /api/fair/projects/{project_id}               |   —    |   ✓   | Project detail |
| PATCH  | /api/fair/projects/{project_id}               |   —    |   ✓   | Update project |
| DELETE | /api/fair/projects/{project_id}               |   —    |   ✓   | Delete project (204) |
| GET    | /api/fair/projects/{project_id}/file          |   —    |   ✓   | Download project file |
| POST   | /api/fair/projects/{project_id}/balloons      |   —    |   ✓   | Create balloon (201) |
| POST   | /api/fair/projects/{project_id}/balloons/reorder | —   |   ✓   | Reorder balloons |
| GET    | /api/fair/balloons/{balloon_id}               |   —    |   ✓   | Single balloon |
| PATCH  | /api/fair/balloons/{balloon_id}               |   —    |   ✓   | Update balloon |
| DELETE | /api/fair/balloons/{balloon_id}               |   —    |   ✓   | Delete balloon (204) |

### Signage — pairing (`/api/signage/pair`)

Per-route gating (documented exception to the router-level rule — see module docstring + dep-audit test SGN-BE-09).

| Method | Path                                        | Auth | Notes |
|--------|---------------------------------------------|------|-------|
| POST   | /api/signage/pair/request                   | public (rate-limited) | Mint 10-minute pairing code (201) |
| GET    | /api/signage/pair/status                    | public | Poll pairing status; delivers device JWT exactly once, then deletes the session row |
| POST   | /api/signage/pair/claim                     | Admin | Bind pending code to a new device (204) |
| POST   | /api/signage/pair/devices/{device_id}/revoke | Admin | Set `revoked_at` — idempotent (204) |

### Signage — player (`/api/signage/player`, Device JWT)

Router-level `get_current_device` gate; no user-auth on these routes.

| Method | Path                                            | Auth   | Notes |
|--------|-------------------------------------------------|--------|-------|
| GET    | /api/signage/player/playlist                    | Device | Tag-resolved playlist envelope; ETag + `If-None-Match` → 304 |
| POST   | /api/signage/player/heartbeat                   | Device | Updates presence; response carries a freshly rolled device JWT |
| GET    | /api/signage/player/stream                      | Device | SSE: `{event, playlist_id, etag}` frames, 15s pings |
| GET    | /api/signage/player/asset/{media_id}            | Device | Media asset bytes |
| GET    | /api/signage/player/asset/{media_id}/slide/{idx} | Device | Converted PPTX slide PNG |
| GET    | /api/signage/player/calibration                 | Device | Per-device display calibration |

### Signage — admin (`/api/signage`, Admin-only)

One router-level admin gate in `backend/app/routers/signage_admin/__init__.py` (D-01).

| Method | Path                                              | Viewer | Admin | Notes |
|--------|---------------------------------------------------|:------:|:-----:|-------|
| GET    | /api/signage/analytics/devices                    |   —    |   ✓   | Bucketed device uptime analytics |
| PATCH  | /api/signage/media/{media_id}                     |   —    |   ✓   | Update media metadata; notifies affected devices |
| DELETE | /api/signage/media/{media_id}                     |   —    |   ✓   | 204; 409 `{detail, playlist_ids}` if referenced |
| POST   | /api/signage/media/pptx                           |   —    |   ✓   | PPTX upload + background PNG conversion (201) |
| GET    | /api/signage/media/{media_id}/slide/{idx}         |   —    |   ✓   | Admin preview of converted slide |
| POST   | /api/signage/media/{media_id}/reconvert           |   —    |   ✓   | Re-run PPTX conversion (202) |
| DELETE | /api/signage/playlists/{playlist_id}              |   —    |   ✓   | 204; 409 `{detail, schedule_ids}` if scheduled |
| PUT    | /api/signage/playlists/{playlist_id}/items        |   —    |   ✓   | Bulk-replace playlist items |
| PATCH  | /api/signage/devices/{device_id}/calibration      |   —    |   ✓   | Update device calibration |
| GET    | /api/signage/resolved/{device_id}                 |   —    |   ✓   | Resolved playlist preview for a device |
| GET    | /api/signage/admin/stream                         |   —    |   ✓   | SSE for the admin UI |

### Public / embed / infrastructure

| Method | Path                                       | Auth   | Notes |
|--------|--------------------------------------------|--------|-------|
| GET    | /health                                    | public | DB ping; 503 if unavailable |
| GET    | /docs                                      | public | OpenAPI UI (no auth) |
| GET    | /openapi.json                              | public | OpenAPI schema (no auth) |
| GET    | /api/auth/forward                          | public | Caddy `forward_auth` target (v1.48). Validates `directus_session_token` cookie locally with PyJWT; on success returns `X-Remote-User: <email>`. Public by design — IS the auth gate for embedded apps. Hidden from the OpenAPI schema. |
| GET    | /api/auth/clear-cookies                    | public | One-shot endpoint that expires stale `directus_*` cookies and 303-redirects to `/login`. Used to migrate browsers from v1.46/v1.47 cookie mode to v1.48 session mode. Hidden from the OpenAPI schema. |
| GET    | /api/settings/logo/public                  | public | Logo bytes for unauthenticated surfaces (login page, kiosks) |
| GET    | /api/hr/embed/birthdays/this-week          | public | Kiosk iframe mirror of the auth'd HR route |
| GET    | /api/hr/embed/joiners/recent               | public | Kiosk iframe mirror of the auth'd HR route |
| GET    | /api/hr/embed/employees/{employee_id}/photo | public | Kiosk iframe mirror of the auth'd HR route |
| GET    | /api/worldcup/embed/today                  | public | Today's World Cup matches for the `/embed/worldcup` kiosk page. Server-side proxy of football-data.org with TTL cache (`services/worldcup_feed.py`); returns `{refresh_seconds, error: "not_configured"}` until an API key is saved in settings |
| GET    | /player, /player/{path}                    | public | Static signage player SPA bundle (mounted only when built) |

## Error Shapes

| HTTP | Condition | Body |
|------|-----------|------|
| 401  | Missing or invalid JWT (user or device) | `{"detail": "invalid or missing authentication token"}` |
| 403  | Valid JWT, Viewer role on a mutation route | `{"detail": "admin role required"}` |
| 409  | Signage media delete blocked by playlist references | `{"detail": ..., "playlist_ids": [...]}` (flat JSONResponse, not HTTPException) |
| 409  | Signage playlist delete blocked by schedules | `{"detail": ..., "schedule_ids": [...]}` (flat JSONResponse) |
| 422  | Upload with wrong file extension / Personio credentials not configured | `{"detail": "<message>"}` |

## Verification

- Automated: `cd backend && python -m pytest tests/test_rbac.py -v`
- Public-route allowlist: `backend/tests/test_admin_gate_audit.py::ADMIN_GATE_ALLOWLIST`
- Source of truth: `backend/app/security/directus_auth.py::require_admin` (the dependency) + router registrations in `backend/app/main.py` and decorators in `backend/app/routers/` (incl. the `signage_admin/` package)
