# KPI

A Dockerized multi-domain KPI platform with Sales and HR dashboards. Uploads tab-delimited ERP export files into PostgreSQL for Sales KPIs, and syncs Personio HR data for HR KPIs — all visualized on a bilingual (DE/EN) interactive dashboard with dark mode. Built for internal team use.

**Core value:** Upload a data file and immediately see sales/revenue KPIs visualized on a dashboard — zero friction from raw data to insight.

---

## Features

### Sales Dashboard
- **KPI Cards** — Total revenue, average order value, total orders with concrete period-over-period delta badges (e.g. `vs. March 2025`, `vs. Q1 2025`, `vs. 2024`)
- **Revenue Chart** — Monthly bar or area chart with prior-period overlay; X-axis shows month names or calendar weeks depending on selected date range
- **Sales Data Table** — Sortable columns (order #, customer, project, date, total, remaining) with global search
- **Date Range Filter** — This month, this quarter, this year, all time (fixed SubHeader below navbar)

### HR Dashboard
- **5 HR KPI Cards** — Overtime ratio, sick leave ratio, fluctuation, skill development, revenue per production employee; each with concrete delta badges matching the Sales ramp
- **12-Month Trend Charts** — Area or bar charts (toggle) for overtime, sick leave, fluctuation, revenue/employee with configurable target reference lines (Sollwerte)
- **Employee Table** — Filtered by departments selected in Personio settings; shows total worked hours, overtime hours, and overtime ratio per employee for the current month
- **Employee Filters** — Segmented toggle: with overtime / active / all

### Settings
- **Appearance** — App name, logo upload (SVG/PNG/JPG/WebP), 6 semantic color tokens (oklch) with live WCAG contrast badges
- **Personio Integration** — Fernet-encrypted API credentials, configurable sync interval (manual/1h/6h/24h), auto-sync via APScheduler, credential test, on-demand refresh
- **Multi-Select Config** — Checkbox lists for sick leave absence types, production departments, and skill attribute keys
- **HR KPI Targets** — Set target values (Sollwerte) displayed as dashed reference lines on HR trend charts
- **Language** — DE/EN toggle stored in localStorage (no server round-trip)
- **Dark Mode** — Sun/moon toggle in navbar; OS `prefers-color-scheme` default + localStorage override; pre-hydration IIFE avoids flash-of-unstyled-content

### App Launcher
- **iOS-style entry point at `/`** — After login, users land on a grid of app icons rather than directly in a dashboard; dashboards live at `/sales`, `/hr`, and `/sensors`
- **Active KPI Dashboard tile** — Rounded-corner 120×120px card with icon only; label sits below the tile (iOS-style); click navigates to `/sales`
- **Sensors tile** — Admin-only environmental monitoring dashboard with live temperature/humidity readings from SNMP devices
- **Coming-soon placeholders** — Greyed tiles (40% opacity, non-clickable) for future apps
- **Role-aware scaffold** — Admin-only tiles can be added without structural changes; Viewer-role users see only tiles without the `admin` flag
- **Minimal launcher chrome (v1.19)** — Top header is identity-only: brand (clickable → launcher), breadcrumb trail (`Apps › Section › …`), theme toggle, language toggle, and user menu. The user menu dropdown holds Docs, Settings, and Sign-out. All page-scoped controls (SALES/HR toggle, date-range filter, upload, Jetzt-messen, etc.) live in the per-route SubHeader below the top chrome

### Digital Signage (v1.16+)
- **Kiosk Player** — Separate Vite entry served at `/player/` on the backend; <200 KB gz entry (lazy `PdfPlayer` + `pdf` chunks), PWA with precached app shell; boots to a 256px monospace 6-digit pairing code on first run
- **Admin UI at `/signage`** — Media (image/video/PDF/PPTX/URL/HTML), Playlists (drag-reorder items, set per-item duration), Devices (pair, tag, revoke), Schedules (time-windowed playlist targeting); SegmentedControl sub-nav
- **Tag-Based Targeting** — Playlists target tags, devices carry tags; resolver picks the highest-priority matching playlist per device
- **Time-Based Scheduling (v1.18)** — Schedule rows bind a playlist to weekday mask + HH:MM start/end + priority; resolver picks the highest-priority matching schedule for the current weekday/time, falling back to the always-on tag resolver when no window matches. Timezone from app settings; SSE `schedule-changed` invalidation pushes changes to connected players.
- **Live Updates via SSE** — Admin mutations fan out to connected players via per-device EventSource queues; 45s client watchdog + 30s polling fallback when the stream goes silent
- **Format Handlers** — Images with fade, videos `muted autoplay playsinline`, PDF pages with 200ms crossfade via react-pdf, sandboxed `<iframe>` for URL and nh3-sanitized HTML, PPTX rendered as an image sequence after LibreOffice conversion
- **Pi Kiosk Provisioning** — Single `scripts/provision-pi.sh` brings a fresh Bookworm Lite 64-bit Pi to a paired, playing kiosk; dedicated non-root `signage` user; systemd user services with labwc + Chromium kiosk flags
- **Offline-Resilient Sidecar** — `pi-sidecar/` FastAPI service on the Pi proxy-caches `/api/signage/player/playlist` and media bytes to `/var/lib/signage/`; 5-minute Wi-Fi drop keeps the loop running; auto-reconnect within 30s
- **Analytics-Lite (v1.18)** — Devices table shows `Uptime 24 h` and `Missed windows 24 h` badges, computed from a 25 h-retention `signage_heartbeat_event` log; 30 s polling + focus refetch
- **Bilingual Admin Guide + Operator Runbook** — `frontend/src/docs/{en,de}/admin-guide/digital-signage.md` covers onboarding, media, playlists, schedules, analytics, offline behavior, PPTX font-embed tips; `docs/operator-runbook.md` carries the systemd units, Chromium flag set, and recovery procedures

### Sensor Monitoring (v1.15+)
- **Live Sensor Dashboard** — KPI cards per sensor with current temperature/humidity, threshold-aware badges, stacked time-series charts with reference lines
- **Time-Window Selector** — View 1h, 6h, 24h, 7d, or 30d windows on sensor readings with gap-aware rendering
- **Poll-Now Button** — Trigger immediate sensor poll with live refresh of cards and charts; includes delta badges vs. 1h and 24h ago
- **Health Status Chip** — Per-sensor "OK since Xh" or "Offline since X min" indicator computed from SNMP poll log
- **Admin Settings Sub-Page** — `/settings/sensors` for CRUD operations on sensors, polling interval tuning, global temperature/humidity thresholds
- **SNMP Walk Tool** — OID discovery utility for network sensor enumeration; click-to-assign discovered OIDs to sensor fields
- **SNMP Probe Button** — Per-sensor connectivity validation with live temperature/humidity test result
- **Encrypted Community Strings** — Fernet-encrypted at rest, write-only secrets (never displayed post-save, shown as `••••••`)
- **Bilingual Admin Guide** — Complete operational runbook (DE/EN) with onboarding workflows, threshold configuration, polling interval tuning, and Docker network troubleshooting

### In-App Documentation
- **Role-Aware Docs** — Library icon in navbar opens /docs; Admins see User Guide + Admin Guide sections, Viewers see User Guide only
- **User Guide** — 5 articles: uploading data, Sales dashboard, HR dashboard, filters & controls, language & dark mode
- **Admin Guide** — 4 articles: system setup (Docker Compose), architecture overview, Personio integration, user management (Directus roles)
- **Bilingual Content** — All 22 articles available in DE and EN, switching with the app's language setting
- **Markdown Rendering** — react-markdown + rehype plugins for syntax-highlighted code blocks, clickable heading anchors, and dark-mode-aware prose
- **Table of Contents** — Auto-generated from article headings with Intersection Observer scroll tracking

### General
- **Bilingual** — Full DE/EN i18n parity (CI-enforced key-count equality + "du"-tone guard) with informal "du" tone for German
- **Theming** — Settings-driven color palette applied via CSS custom properties; chart colors follow primary/muted tokens; class-strategy dark mode via Tailwind v4
- **Unified Layout** — Sales, HR, Upload, and Settings share the same `max-w-7xl` page container
- **Breadcrumb Navigation (v1.19)** — Top chrome renders `Apps › Section › [Subsection]` derived from the current route; replaces the prior last-dashboard back button
- **Consolidated UI Primitives (v1.19)** — Single canonical `Input`, `Select`, `Button`, `Textarea`, `Dropdown`, `Toggle`, `SectionHeader`, `DeleteButton`, and `DeleteDialog` under `components/ui/`, driving every form control and destructive action in the app
- **Auto-Refresh** — Dashboard re-fetches all queries after successful upload or Personio sync via TanStack Query prefix invalidation

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Database | PostgreSQL 17 (Alpine) |
| Backend | FastAPI, SQLAlchemy 2.0 (async), asyncpg, Pydantic v2 |
| Migrations | Alembic |
| Parsing | pandas 3.0 with German locale handling |
| Frontend | React 19, TypeScript, Vite 8 |
| Styling | Tailwind CSS 4 (class-strategy dark mode), shadcn/ui (base-ui primitives) |
| Routing | wouter |
| Charts | Recharts |
| State | TanStack Query v5 |
| i18n | react-i18next (flat dotted keys, `keySeparator: false`) |
| Scheduler | APScheduler (in-process) |
| External | Personio API (employees, attendances, absences) |
| Infrastructure | Docker Compose v2 |

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/johann-b82/kpi-dashboard.git
cd kpi-dashboard

# 2. Create your .env file from the template
cp .env.example .env
# Edit .env with your credentials

# 3. Bring the stack up
docker compose up --build
```

Once containers are healthy:

- **App (via Caddy reverse proxy):** http://localhost/
- **FastAPI (direct dev):** http://localhost:8000
- **OpenAPI docs:** http://localhost:8000/docs
- **Vite dev server (direct dev):** http://localhost:5173
- **Directus admin UI:** http://localhost:8055 (loopback-only; Caddy also
  exposes the Directus API same-origin at http://localhost/directus for the SPA)

Phase 64 added a Caddy reverse proxy (`caddy:2-alpine`) fronting the stack
on port 80. Normal operator + LAN workflows use `http://<host>/`; the
direct-port exposures above remain for developer ergonomics.

### Prerequisites

- Docker and Docker Compose v2
- Personio API credentials (optional, for HR features)

### Environment Variables

| Variable | Description |
|----------|-------------|
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | Database name |
| `FERNET_KEY` | Encryption key for Personio credentials |

---

## Architecture

**Architecture (v1.22):** Directus serves shape (CRUD on sales,
employees, signage admin); FastAPI serves compute (upload, KPIs,
sync, SSE, calibration). See [ADR-0001](./docs/adr/0001-directus-fastapi-split.md).

```
docker compose up
  |
  +-- db       (postgres:17-alpine)           --> internal :5432
  +-- migrate  (alembic upgrade head)         --> exits after migration
  +-- api      (uvicorn + FastAPI)            --> :8000
  +-- frontend (vite dev server)              --> :5173 (proxies /api to :8000)
  +-- directus (directus:11.x identity)       --> 127.0.0.1:8055 (loopback)
  +-- caddy    (reverse proxy)                --> :80
        / → frontend:5173 (admin SPA + /login + /signage/pair + launcher)
        /api/* → api:8000 (FastAPI; SSE passthrough via flush_interval -1)
        /directus/* → directus:8055 (prefix stripped; same-origin cookies)
        /player/* → frontend:5173 (kiosk bundle)
```

### Project Structure

```
kpi-light/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── defaults.py          # Canonical default settings
│   │   ├── routers/
│   │   │   ├── uploads.py       # File upload, upload history
│   │   │   ├── kpis.py          # Sales KPI aggregation + chart
│   │   │   ├── hr_kpis.py       # HR KPI current + 12-month history
│   │   │   ├── hr_overtime.py   # /api/data/employees/overtime compute roll-up (v1.22)
│   │   │   ├── settings.py      # App settings + Personio options
│   │   │   ├── sync.py          # Personio sync trigger + meta
│   │   │   ├── sensors.py       # Sensor CRUD, SNMP probe/walk, polling endpoints
│   │   │   ├── signage_admin/   # Compute-only signage surface (v1.22): playlist DELETE, bulk playlist-items PUT, device calibration PATCH, resolved/{device_id}, analytics
│   │   │   ├── signage_player.py # Kiosk-facing playlist + asset + SSE stream
│   │   │   └── signage_pair.py  # Device JWT minting + pairing flow
│   │   └── services/
│   │       ├── kpi_aggregation.py
│   │       ├── hr_kpi_aggregation.py
│   │       ├── snmp_poller.py   # SNMP polling, walk, probe utilities
│   │       └── signage_pg_listen.py # Postgres LISTEN/NOTIFY → SSE bridge (v1.22)
│   ├── alembic/                 # Migration chain
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── pages/               # LauncherPage, DashboardPage, HRPage, SensorsPage, UploadPage, SettingsPage, SensorsSettingsPage, DocsPage
│       ├── components/
│       │   ├── dashboard/       # KpiCard, RevenueChart, HrKpiCharts, SalesTable, EmployeeTable
│       │   ├── sensors/         # SensorStatusCards, SensorTimeSeriesChart, PollNowButton
│       │   ├── docs/            # MarkdownRenderer, DocsSidebar, TableOfContents
│       │   ├── settings/        # PersonioCard, CheckboxList, HrTargetsCard, ColorPicker, LogoUpload, ActionBar, SensorRowForm, PollIntervalCard, ThresholdCard, SnmpWalkCard, SensorProbeButton
│       │   ├── NavBar.tsx, ThemeProvider.tsx, DropZone.tsx
│       │   └── ui/              # shadcn primitives (checkbox, segmented-control, etc.)
│       ├── docs/                # Markdown articles (en/ and de/ subdirectories)
│       ├── hooks/               # useSettings, useSettingsDraft, useTableState, useUnsavedGuard
│       ├── lib/                 # api.ts, queryKeys.ts, color.ts, dateUtils.ts, defaults.ts
│       └── locales/             # en.json, de.json
│
├── docker-compose.yml
├── .env.example
└── docs/superpowers/            # superpowers specs/ and plans/ (active workflow)
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings` | App settings (colors, branding, Personio config, KPI targets) |
| PUT | `/api/settings` | Update settings |
| POST | `/api/settings/logo` | Upload logo |
| GET | `/api/settings/personio-options` | Available absence types, departments, skill attributes |
| POST | `/api/upload` | Upload ERP sales file |
| GET | `/api/uploads` | List upload batches |
| DELETE | `/api/uploads/{id}` | Delete upload batch |
| GET | `/api/kpis` | Sales KPI summary with comparison periods |
| GET | `/api/kpis/chart` | Sales chart data (monthly, with prior-period overlay) |
| GET | `/api/kpis/latest-upload` | Latest upload timestamp |
| GET | `/api/hr/kpis` | HR KPI values (current month + comparisons) |
| GET | `/api/hr/kpis/history` | HR KPI 12-month history for trend charts |
| GET | `/api/data/employees/overtime` | Per-employee total-hours / overtime roll-up over `?date_from&date_to` (compute-only; row data comes from Directus `personio_employees`, v1.22) |
| POST | `/api/sync` | Trigger Personio data sync |
| POST | `/api/sync/test` | Test Personio credential validity |
| GET | `/api/sync/meta` | Last sync status and counts |
| GET | `/api/sensors` | List all sensors (admin-only) |
| POST | `/api/sensors` | Create a new sensor (admin-only) |
| PATCH | `/api/sensors/{id}` | Update sensor config (admin-only) |
| DELETE | `/api/sensors/{id}` | Delete sensor (admin-only) |
| GET | `/api/sensors/{id}/readings` | Sensor reading history (filterable by hours window) |
| GET | `/api/sensors/status` | Sensor health status from poll log (admin-only) |
| POST | `/api/sensors/poll-now` | Trigger immediate poll of all sensors (admin-only) |
| POST | `/api/sensors/snmp-probe` | Test SNMP connectivity with config (admin-only) |
| POST | `/api/sensors/snmp-walk` | Discover OIDs on network with SNMP walk (admin-only) |
| POST | `/api/signage/pair/request` | Kiosk requests a pairing session (unauthenticated) |
| GET | `/api/signage/pair/status` | Kiosk polls until admin claims (unauthenticated) |
| POST | `/api/signage/pair/claim` | Admin claims a pairing code → binds device JWT (admin-only) |
| POST | `/api/signage/pair/devices/{id}/revoke` | Revoke a device token (admin-only) |
| GET,POST,PATCH,DELETE | `/api/signage/media` | Admin media CRUD (admin-only) |
| DELETE | `/api/signage/playlists/{id}` | Delete playlist; structured `409 {detail, schedule_ids}` when referenced (admin-only; CRUD list/create/update via Directus, v1.22) |
| PUT | `/api/signage/playlists/{id}/items` | Atomic bulk DELETE+INSERT of playlist items (admin-only; items GET via Directus, v1.22) |
| PATCH | `/api/signage/devices/{id}/calibration` | Update rotation/HDMI mode/audio (admin-only; device CRUD list/create/rename/delete/tags via Directus, v1.22) |
| GET | `/api/signage/resolved/{device_id}` | Schedule-resolved playlist for a device — `{current_playlist_id, current_playlist_name, tag_ids}` — merged client-side with Directus rows (admin-only, v1.22) |
| GET | `/api/signage/player/playlist` | Tag-resolved playlist envelope for the kiosk (device-auth) |
| GET | `/api/signage/player/asset/{media_id}` | Device-auth'd media passthrough (device-auth) |
| GET | `/api/signage/player/stream` | SSE stream of playlist-change events (device-auth, `?token=` query) |
| POST | `/api/signage/player/heartbeat` | Kiosk presence beacon (device-auth) |
| GET | `/api/signage/analytics/devices` | Per-device uptime + missed-window counts over the last 24 h (admin-only, v1.18) |

**Migrated to Directus (v1.22):** `signage_tags`, `signage_schedules`, `signage_playlists` (list/create/rename/re-tag), `signage_playlist_items` (GET), `signage_devices` (list/get/rename/tags/delete), `sales_records`, `personio_employees`, current-user `readMe`. Frontend reaches these via the Directus SDK (same-origin at `/directus/*` through Caddy); the surviving FastAPI surface above is compute-only.

**Junction-table PKs (v1.24):** `signage_playlist_tag_map` and `signage_device_tag_map` carry a surrogate `id SERIAL PRIMARY KEY` with a `UNIQUE` constraint on the original `(playlist_id, tag_id)` / `(device_id, tag_id)` pair. Composite primary keys are not exposable by Directus, so the junction tables are now first-class collections while the no-duplicate-pairs invariant is preserved.

---

## Database Migrations

Migrations run automatically via the `migrate` compose service on `docker compose up`. To generate a new migration:

```bash
docker compose exec api alembic revision --autogenerate -m "describe change"
docker compose build migrate
docker compose up migrate
```

> **Important:** Never call `Base.metadata.create_all()` — always go through Alembic.

---

## Development

The compose stack mounts `./backend` and `./frontend` as volumes:

- **Backend:** `uvicorn --reload` picks up Python changes automatically
- **Frontend:** Vite HMR picks up React/TypeScript changes automatically

```bash
docker compose exec api python -c "..."            # backend commands
docker compose exec frontend npx tsc --noEmit       # type-check frontend
docker compose exec db psql -U kpi_user -d kpi_db   # database shell
```

---

## Testing

### Backend unit/integration tests

```bash
docker compose exec api pytest
```

### End-to-end rebuild persistence smoke test

Prereq (one-shot, after any `@playwright/test` version bump):
```bash
cd frontend && npx playwright install chromium
```

Run the full rebuild persistence harness (seeds settings, rebuilds the stack, asserts persistence, visual check via Playwright):
```bash
./scripts/smoke-rebuild.sh
```

Exits 0 on success; non-zero and prints the failing step on failure. The harness preserves `postgres_data` (it uses `docker compose down`, NOT `down -v`).

---

## Version History

<details>
<summary><strong>v1.11-directus</strong> — 2026-04-15 — Auth + RBAC via self-hosted Directus</summary>

### What changed

- **Added: Directus 11 container.** A single `directus/directus:11` service runs alongside the existing Postgres, providing email/password login, two built-in roles (`Admin`, `Viewer`), and an admin UI at `http://localhost:8055` for user management. FastAPI verifies the Directus-issued JWT (HS256 shared secret) on every `/api/*` request; mutation routes require `Admin`, read routes are open to both roles.
- **Added: nightly `pg_dump` backup sidecar.** A `backup` service in `docker-compose.yml` dumps the database nightly at 02:00 local time to `./backups/kpi-YYYY-MM-DD.sql.gz`, with 14-day rolling retention. A positional-arg `./scripts/restore.sh <dump-file>` streams a dump back into the running `db` container.
- **Added: `docs/setup.md`.** A linear bring-up tutorial for first-time operators, including the Viewer→Admin promote click-path and the backup/restore procedure.

### What was rejected

- **Dex + oauth2-proxy + NPM auth_request** (Phase 32, previous attempt) — abandoned. Three moving parts to configure (Dex provider, oauth2-proxy sidecar, NGINX Proxy Manager auth_request directive) to get one sign-in page. Preserved on branch `archive/v1.12-phase32-abandoned` for reference only.
- **Supabase** — evaluated, rejected. Full Supabase is a 5-service stack (Postgres, Auth, PostgREST, Realtime, Studio) when the project only needs sign-in and role assignment. Directus delivers the same outcome in one container on the existing database.

### What was dropped

- **Outline wiki** — removed from the stack entirely. The earlier v1.11/v1.12 plan was to share SSO between KPI Light and Outline via Dex. With Dex gone, the Outline use case is out of scope for this milestone. Existing Outline content (if any was deployed) is unaffected at the data level but no longer managed by this repo.

### Impact for users

- First-time login: browse to `/login`, enter email + password.
- Viewer users see the dashboards but no upload/sync/save controls — those are admin-only and are hidden from the DOM entirely, not just disabled.
- Administrators manage users via Directus at `http://localhost:8055` (direct) or through the proxy at `http://localhost/directus/admin` (v1.21+).

</details>

| Version | Date | Description |
|---------|------|-------------|
| v1.24 | 2026-04-30 | Test Fixture + Frontend Build Hygiene — paid down test/build debt that had been masking a broken `pytest -q` and `npm run build` since the initial commit. Phase A: added `admin_client` / `viewer_client` fixtures to `backend/tests/conftest.py` (mint Directus JWTs via shared `tests/_auth.py`), migrated 7 older test files (settings, KPI, rebuild seed/assert/cleanup) onto them, and registered the `integration` pytest marker so DB-LISTEN/Directus-CRUD/host-docker tests skip by default (`pytest -m integration` opts in). `pytest -q` now reports 366 passed, 6 skipped, 59 deselected on a clean container. Phase B: added `@types/node` so the contract tests compile, replaced `void → null` casts in `signageApi.ts` with explicit `await; return null`, removed `default_language` carries-over from the schema, fixed an `EmployeeTable` `string \| undefined` mismatch by widening the hook signature with `enabled` gating, and corrected vitest mock signatures in `error-contract.test.ts`. Phase C: rewired smoke-rebuild's Playwright step behind `SMOKE_REBUILD_E2E=1` (the SPA-side persistence check needs Directus cookie-mode auth follow-up), updated the test for the `default_language` removal, and extended `.github/workflows/ci.yml` with a full `pytest -q` + `npm run build` step pair so this debt cannot re-accumulate. |
| v1.23 | 2026-04-30 | Router/Compute Boundary Cleanup — formalized the Directus = shape / FastAPI = compute split begun in v1.22. Phase A deduplicated four `notify_*` helpers in `signage_broadcast.py`. Phase B introduced a router-level admin-gate convention (CI-enforced via `test_admin_gate_audit.py`) and split the uploads router. Phase C migrated four remaining CRUDs to Directus (`GET /api/uploads`, `GET/POST /api/signage/media`, `GET /api/signage/media/{id}`) with contract fixtures + CI disallow-rules. Phase D published the Compute-Justified Rubric in ADR-0001, tagged 15 compute modules with `Compute-justified:` clauses, added `test_compute_justified_rubric.py` CI guard, and documented the choose-where-to-put-it decision tree in `architecture.md`. Two follow-up infra fixes (`d57fb7d`, `79846ff`) made Directus bootstrap idempotent for cold-boot and properly created the `signage_schedules` validation Flow. v1.23's D-5 verification was scoped to the contract guards introduced by this version; full-suite green is deferred to v1.24 (test fixture + frontend build hygiene). |
| v1.22 | 2026-04-25 | Backend Consolidation — Directus-First CRUD — moved ~25 pure-CRUD FastAPI endpoints (`/api/me`, sales/employee row reads in `data.py`, signage admin tags/schedules/playlists/devices) to Directus collections on the shared Postgres, leaving FastAPI focused on compute (upload, KPIs, Personio sync, SSE, calibration, bulk playlist-item replace, PPTX, device-JWT minting, analytics). New Postgres `LISTEN/NOTIFY` → asyncpg → SSE bridge fans out Directus-originated mutations to Pi players within 500 ms across 5 signage tables. Frontend `signageApi.ts` adapter wraps Directus SDK calls and normalizes errors to the existing `ApiErrorWithBody` contract; 10 contract-snapshot fixtures lock the wire shape. New compute-only endpoints: `GET /api/data/employees/overtime` and `GET /api/signage/resolved/{device_id}`. CI guards prevent any of the migrated routes from reappearing; OpenAPI paths snapshot + `DB_EXCLUDE_TABLES` superset check freeze the surface. ADR-0001 documents the Directus = shape / FastAPI = compute split. |
| v1.21 | 2026-04-24 | Signage Calibration + Build Hygiene + Reverse Proxy — per-device runtime calibration of signage Pis (rotation, HDMI mode, audio on/off) editable from the admin UI and applied live by the Pi sidecar via `wlr-randr` + WirePlumber; `/var/lib/signage/calibration.json` persistence + bounded wayland-wait boot replay (CAL-PI-07 real-Pi walkthrough waived pending per-device diagnostic). `docker compose build frontend` now exits 0 via `--legacy-peer-deps` workaround for `vite@8` / `vite-plugin-pwa@1.2.0`. New Caddy 2 reverse proxy on `:80` fronts admin SPA, FastAPI (SSE-safe), Directus (prefix-stripped, no CORS), and the kiosk bundle — `http://<lan-ip>/login` finally works from any LAN host; Pi `:80` URLs in `provision-pi.sh` resolve. Authentik references removed from docs now that Directus is the committed identity layer |
| v1.20 | 2026-04-22 | HR Date-Range Filter + TS Cleanup — shared `DateRangeFilter` wired into `/hr` (KPI cards, charts, employee table); backend `date_from`/`date_to` on all HR endpoints with adaptive daily/weekly/monthly/quarterly bucketing; fluctuation denominator switched to avg-active-headcount; Personio sync reworked to full first-run backfill + incremental `max(stored_date)-14d` with 429 exponential backoff and weekly default cadence; HR delta-badge + chart-axis naming matched to Sales; `/sales`-only upload icon; Balken/Linien toggle ordering unified. Phase 61 closed 31 pre-existing TypeScript errors across 9 files — `npm run build` now exits 0 with zero `error TS` |
| v1.19 | 2026-04-22 | UI Consistency Pass 2 — new `Toggle` primitive (pill + animated indicator, radiogroup a11y, reduced-motion-aware) drives all 2-option switches; consolidated `Input`/`Select`/`Button`/`Textarea`/`Dropdown` primitives on the `h-8` height token with shared focus/disabled/invalid states; identity-only top header with breadcrumb trail + `UserMenu` dropdown (Docs/Settings/Sign-out); `SectionHeader` + shared `DeleteButton`/`DeleteDialog` across every admin surface; `/sensors` page body slimmed to cards+chart with picker and Jetzt-messen hoisted to SubHeader; DE/EN parity and dark-mode sweep across 13 migrated surfaces with CI guards |
| v1.18 | 2026-04-21 | Pi Polish + Scheduling — player bundle back under 200 KB gz via dynamic `PdfPlayer` import; hardware E2E Scenarios 4 + 5 validated on `provision-pi.sh`-provisioned Pi; time-based playlist schedules (weekday mask + HH:MM windows + priority) with admin UI and SSE invalidation; Analytics-lite uptime/missed-window badges on the Devices table |
| v1.17 | 2026-04-21 | Pi Image Release path (later retired in v1.18) — installer library + systemd unit templates consolidated in `scripts/lib/signage-install.sh`; `.img.xz` distribution path removed in favour of `provision-pi.sh`-only |
| v1.16 | 2026-04-20 | Digital Signage — Pi kiosk + admin UI: tag-targeted playlists, SSE live updates, Python sidecar offline cache on the Pi, bilingual admin guide + operator runbook, one-script Bookworm Lite provisioning |
| v1.15 | 2026-04-18 | Sensor Monitor — Live SNMP temperature/humidity readings with KPI cards, time-series charts, admin settings sub-page, SNMP walk/probe tools, encrypted community strings, bilingual admin guide |
| v1.14 | 2026-04-17 | App Launcher — iOS-style `/` entry point with 4-tile grid, role-aware scaffold, bilingual labels, AuthGate post-login redirect |
| v1.13 | 2026-04-17 | In-App Documentation — role-aware docs with Markdown rendering, 22 bilingual articles, TOC with scroll tracking |
| v1.12 | 2026-04-16 | Chart Polish & Rebrand — year-aware x-axis labels, gap-filled month spines, "KPI Dashboard" rebrand, login page restyling |
| v1.11-directus | 2026-04-15 | Auth + RBAC via self-hosted Directus; nightly pg_dump backups; Outline wiki and Dex/oauth2-proxy path dropped |
| v1.10 | 2026-04-14 | UI Consistency Pass — unified delta labeling (concrete period names, DE/EN parity) + page layout parity across Sales/HR/Upload/Settings; merged Appearance card; contextual back button |
| v1.9 | 2026-04-14 | Dark Mode & Contrast — Tailwind v4 class-strategy dark mode, CSS-variable tokens, WCAG AA audit, no theme-flash pre-hydration IIFE |
| v1.8 | 2026-04-12 | Employee table: worked hours, overtime ratio, department filter, active/all toggle |
| v1.7 | 2026-04-12 | Data tables, HR KPI 12-month trend charts, chart colors from settings, area charts, UI polish |
| v1.6 | 2026-04-12 | Multi-select checkbox lists for Personio config, JSONB array migration, language moved to localStorage |
| v1.5 | 2026-04-12 | Unified pill-shaped segmented controls across all toggles |
| v1.4 | 2026-04-12 | Navbar polish, SubHeader with route-aware freshness indicator |
| v1.3 | 2026-04-12 | HR KPI dashboard, Personio integration with encrypted credentials, auto-sync |
| v1.2 | 2026-04-12 | Period-over-period delta badges, chart prior-period overlay |
| v1.1 | 2026-04-11 | Branding, settings page, ThemeProvider, i18n bootstrap |
| v1.0 | 2026-04-11 | MVP — Docker stack, ERP file upload, sales dashboard |

---

## License

Internal tool — not currently licensed for external distribution.
