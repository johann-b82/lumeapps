# KPI Light — Architecture

This document captures the top-level component layout of the running stack.
For bring-up / setup see [`setup.md`](./setup.md); for the operator-side
walkthrough see [`operator-runbook.md`](./operator-runbook.md).

---

## Reverse Proxy (Phase 64, v1.21+)

A Caddy 2 reverse proxy (`caddy:2-alpine`) fronts the full stack on port 80.
HTTP only — TLS, external domain routing, and certificate management are
out of scope for this milestone.

**Routes (see `caddy/Caddyfile`):**

| Path         | Upstream          | Prefix handling              | Notes                                                                      |
| ------------ | ----------------- | ---------------------------- | -------------------------------------------------------------------------- |
| `/`          | `frontend:5173`   | Preserved                    | Admin SPA (login, launcher, dashboards, signage admin). Public `/embed/*` kiosk routes (birthdays, joiners, worldcup) also ride this catch-all — they render without a Directus session. |
| `/api/*`     | `api:8000`        | Preserved                    | FastAPI routes live at `/api/...`. SSE passthrough via `flush_interval -1` + 24h `read_timeout`. |
| `/directus/*`| `directus:8055`   | **Stripped** (`handle_path`) | Directus doesn't know it's behind a subpath; it expects bare `/auth`, `/items`, `/assets`, `/server`. |
| `/player/*`  | `api:8000`        | Preserved                    | Kiosk bundle. Built into `frontend/dist/player/` and served by FastAPI as a StaticFiles mount (see `backend/app/main.py`). Vite dev does NOT serve the player entry — routing through FastAPI means the Pi always gets the built bundle. Rebuild with `npm run build:player`. |

**Why Caddy, why this shape:**

- One hostname + one port for LAN clients (admin browser, Pi kiosk, Pi
  sidecar) eliminates CORS and simplifies auth. Directus's httpOnly refresh
  cookie lives on the same origin as the SPA, so it travels on every
  `/directus/*` request without preflight.
- The Directus `CORS_ENABLED` / `CORS_ORIGIN` / `CORS_CREDENTIALS` env vars
  were **removed** from `docker-compose.yml` in Phase 64. With same-origin
  calls there's no cross-origin preflight; if a direct-to-Directus call
  ever reappears it will fail loudly, which is the desired canary.
- SSE passthrough is load-bearing: player + sidecar EventSource clients
  and the backend `/api/signage/player/stream` handler both assume the
  connection survives indefinitely. Caddy's `flush_interval -1` disables
  response buffering and the transport's `read_timeout 24h` prevents the
  default ~30s idle cutoff from killing the stream.

**Direct-port exposures preserved** for developer ergonomics:

- `api:8000` → `0.0.0.0:8000`
- `frontend:5173` → `0.0.0.0:5173`
- `directus:8055` → `127.0.0.1:8055` (loopback only; operator admin UI)

**Frontend Directus SDK** (`frontend/src/lib/directusClient.ts`) defaults
to same-origin `"/directus"` as of Phase 64. `VITE_DIRECTUS_URL` still
overrides for dev workflows that want to bypass the proxy.

---

## Components

```
docker compose up
  |
  +-- db       (postgres:17-alpine)           --> internal :5432
  +-- migrate  (alembic upgrade head)         --> exits after migration
  +-- api      (uvicorn + FastAPI)            --> :8000
  +-- frontend (vite dev server)              --> :5173 (Vite proxies /api in dev)
  +-- directus (directus:11.x identity)       --> 127.0.0.1:8055 (loopback)
  +-- caddy    (reverse proxy)                --> :80 (LAN entry point)
  +-- backup   (pg_dump cron sidecar)         --> writes to ./backups/
```

For deeper detail on any single subsystem (signage, sensors, HR pipeline,
etc.) see the per-phase plans under `.planning/phases/`.

---

## Directus / FastAPI Boundary (v1.22)

Since v1.22 (2026-04), kpi-dashboard splits its backend along a
canonical boundary: **Directus = shape, FastAPI = compute**.

- **Directus serves CRUD** on `sales_records`, `personio_employees`,
  and the signage admin collections (`signage_devices`,
  `signage_playlists`, `signage_playlist_items`, `signage_*_tag_map`,
  `signage_schedules`, `signage_device_tags`). Identity reads via
  `readMe()`.
- **FastAPI serves compute:** file upload + parsing, KPI aggregation,
  Personio/sensor sync (APScheduler), the `signage_player` SSE
  bridge, JWT minting, media + PPTX, calibration PATCH,
  `/api/signage/resolved/{id}`, and the structured-409 `DELETE
  /playlists/{id}` + atomic bulk `PUT /playlists/{id}/items`.
- **Postgres LISTEN/NOTIFY** bridges Directus writes back to SSE so
  Pi players see fan-out within ~500 ms regardless of which writer
  (Directus, psql, FastAPI compute) touched the row. Single-listener
  invariant via `--workers 1`.
- **Alembic** remains the sole DDL owner; Directus stores metadata
  rows only.

Decision recorded in [ADR-0001](./adr/0001-directus-fastapi-split.md).

---

## Sales Ingestion Tables (v1.53 / v1.54)

The Sales dashboard now sources from two ERP-export ingestion tables
(Alembic head is `v1_77_produktion_verzug_target`):

- **`revenues`** (migration `v1_53_revenues`) — Umsatz rows (RG/GS —
  Rechnungsausgang / Gutschrift) from the `AswKpf_RG.txt` ERP export
  (18-col tab-separated, Latin-1), keyed by `Vorgang Nr.` so re-uploads
  upsert on PK. Drives the "Umsatz" KPI card and "Umsatzwachstum" chart;
  GS (credit note) rows carry a negative `wert_eur` and naturally reduce
  the summed total.
- **`auftraege`** (migration `v1_54_auftraege`) — orders from the
  `AswKpf_AUF.txt` export (same shape as the ANG/RG dumps). Drives the
  order-side KPIs (`avg_order_value`, `total_orders`, orders/wk/rep,
  top-3 customer share), replacing the legacy 60-col `Aufträge.txt`
  format. The legacy `sales_records` table stays in place for back-compat
  but no longer drives the dashboard.

Both extend the `upload_batches.kind` check constraint with their
respective discriminator and flow through the FastAPI upload + KPI
aggregation pipeline (compute side of the ADR-0001 boundary).

---

## KPI Domains Beyond Sales & HR (v1.49–v1.77)

Past v1.49 the dashboard grew from Sales + HR into a multi-domain KPI
platform. Each domain follows the same shape: an ERP-export upload feeds
an Alembic-owned ingestion table, a Viewer-readable `/api/<domain>`
router computes the KPI value + history + drill-down list, and a
launcher tile fronts the dashboard. All KPI routers are **Viewer-read**
(router-level `Depends(get_current_user)`, no `require_admin`).

| Domain | Router (prefix) | Core KPI(s) | Migrations |
| ------ | --------------- | ----------- | ---------- |
| Quality | `quality_kpis.py` (`/api/quality`) | Audit findings, customer complaint-rate; per-supplier targets (Sollwerte) | `v1_49`, `v1_59`, `v1_66`, `v1_69` |
| Procurement | `procurement_kpis.py` (`/api/procurement`) | Supplier on-time-delivery (OTD) from goods receipts | `v1_60`, `v1_67`, `v1_68` |
| Finance | `finance_kpis.py` (`/api/finance`) | Material-cost ratio, personnel-cost ratio; both with configurable targets | `v1_70`, `v1_71`, `v1_72` |
| Production | `production_kpis.py` (`/api/production`) | Order delay (Verzug), overdue orders | `v1_76`, `v1_77` (head) |

**Production Verzug** builds on a position-level `AswKpf_AUF` export
(`auftrag_positionen`): an order is *in Verzug* when its latest
delivery-note date exceeds its target date. The `/verzug/overdue` route
surfaces the currently-late orders.

### ATR — Abnahme-/Teile-Reporting (v1.63–v1.65, Admin-only)

The ATR module generates customer weight-acceptance reports. Unlike the
KPI domains it is **compute-heavy and Admin-only** — it stays entirely on
the FastAPI side of the ADR-0001 boundary (file parsing, PDF/DOCX
generation, SMB fileserver I/O), never in Directus.

- **Parts catalog + template** (`atr.py`, `/api/atr`): the parts catalog
  is populated via an Excel preview→commit import; a per-customer report
  template drives the generated documents.
- **Deliveries** (`atr_delivery.py`, `/api/atr/deliveries`): a
  Lieferschein is parsed, its positions matched against the catalog, and
  reviewed before generating the ATR **XLSX** (openpyxl body) + **PDF**
  (LibreOffice UNO print-header) + container-label **DOCX**. Openpyxl
  breaks merged cells on row insert/delete, so the print-header is applied
  via UNO rather than openpyxl.
- **Fileserver** (`atr/fileserver` router in `settings.py`): optional SMB
  drop-folder for input Lieferschein files.

### Fair — trade-fair balloon layout (v1.73–v1.75, Admin-only)

`fair.py` (`/api/fair`, Admin-only) manages trade-fair projects and their
balloon placements (create/reorder), with a per-project file attachment.

---

## World Cup Signage Embed (v1.57)

A public kiosk page at `/embed/worldcup` shows today's World Cup matches
with live scores and a full-screen goal overlay. Like the other
`/embed/*` routes (birthdays, joiners), it short-circuits in the
frontend `RootRouter` before the auth-gated AppShell — kiosks carry no
Directus session.

- **Feed endpoint:** `GET /api/worldcup/embed/today`
  (`backend/app/routers/worldcup.py`) is public (listed in the
  admin-gate allowlist, same rationale as the HR embeds). Compute-
  justified: it proxies football-data.org v4 server-side so the API key
  never leaves the server.
- **Caching:** `backend/app/services/worldcup_feed.py` keeps a
  module-level TTL cache, so one upstream call per refresh interval
  serves every kiosk regardless of screen count. On upstream failure the
  last good data keeps being served with `stale_since` set — a signage
  screen must never go blank.
- **Settings:** migration `v1_57_worldcup` adds two `app_settings`
  columns: `worldcup_api_key_enc` (Fernet-encrypted, like the Personio
  credentials) and `worldcup_refresh_seconds` (default 60). The admin
  settings API exposes `worldcup_has_api_key` (boolean — the key itself
  is write-only via `worldcup_api_key`) and the refresh interval; the
  SPA edits both in the World Cup settings section.
- **Goal detection:** client-side score diff between polls
  (`frontend/src/components/worldcup/goalDetection.ts`). Never fires on
  the first poll after page load (a kiosk restart must not replay old
  goals), skips matches absent from the previous poll (day rollover),
  and ignores downward corrections. Detected goals queue up and play
  sequentially as a 6-second `GoalOverlay`.
- **Polling:** the page polls at the server-configured interval
  (clamped to ≥30 s client-side) via TanStack Query
  `refetchInterval`, so the feed's `refresh_seconds` round-trips into
  the next poll delay.

---

## HR Org Chart & Launcher Hubs (v1.83)

The Organigramm at `/hr/organigramm` renders the reporting hierarchy from
**already-synced Personio data** — no live Personio API call. The HR sync
stores each employee's full Personio payload in `personio_employees.raw_json`;
the supervisor link lives at `attributes.supervisor.value.attributes.id.value`.

`GET /api/hr/org-chart` (`backend/app/routers/hr_kpis.py`, viewer-gated at the
router level) reads active employees and returns each one's `supervisor_id`.
It sits in the HR compute router beside the KPI-aggregation endpoints (the
module docstring already declares `Compute-justified: clause 3`); rather than
exposing table rows verbatim it transforms the nested raw payload into flat
org-chart nodes. The frontend `OrganigrammPage` builds a forest (roots =
no/unknown supervisor, self/cycle guarded) and renders a collapsible tree.

The launcher home (`/`) groups tiles behind two hub pages: a **KPI-Dashboard**
tile → `/kpi` (`KpiDashboardHomePage`, six dashboard tiles — Vertrieb, Einkauf,
Produktion, HR, Qualität, Finanzperspektive) and an **HR** tile → `/hr/home`
(`HrHomePage`, Onboarding + Organigramm). The individual dashboard routes
(`/sales`, `/quality`, `/hr`, …) are unchanged — only their launcher entry
points moved behind the hubs.

---

## Cache Namespace Migration & v22 Purge Flag (Phase 73 CACHE-03)

**Phase:** 73 — Cache Namespace Migration
**Status:** Decision recorded 2026-04-27.
**Related:** ADR-0001 (Directus = shape / FastAPI = compute split, Phase 71 CLEAN-05).

### Namespace contract

TanStack Query keys under `frontend/src/signage/` use these namespaces:

- `['directus', '<collection>', ...]` for Directus-backed reads. Collection name matches the Directus collection slug exactly (e.g. `['directus', 'signage_media']`, `['directus', 'signage_playlists']`, `['directus', 'signage_devices']`, `['directus', 'signage_tags']`, `['directus', 'signage_schedules']`). Item-level keys append the id: `['directus', 'signage_playlists', id]`.
- `['fastapi', ...]` for surviving FastAPI-backed reads. Today's only entry under signage is `['fastapi', 'analytics', 'devices']` (`/api/signage/analytics/devices`); Phase 70 also established `['fastapi', 'resolved', deviceId]` for `/api/signage/resolved/{id}`.
- **No** `['signage', ...]` query keys remain in `frontend/src/signage/` after Phase 73 Plan 01. The legacy `signageKeys.all` factory entry was deleted; `['directus']` would be too broad a prefix to invalidate.

Consumers go through the typed `signageKeys` factory in `frontend/src/lib/queryKeys.ts` so future renames touch one line.

### CI grep guard (CACHE-02)

A pre-stack step in `.github/workflows/ci.yml` (`Guard — no ['signage' query keys in frontend/src/signage/ (CACHE-02)`) fails the build on any literal `['signage'` array head under `frontend/src/signage/`. Lines tagged with the marker `// signage-key-allowed: <reason>` are excluded; expected count today is zero. The marker exists for future flexibility (e.g. a hypothetical FastAPI surface that semantically is "signage").

### `kpi.cache_purge_v22` bootstrap flag — retain with sunset

`frontend/src/bootstrap.ts` runs a one-shot `queryClient.removeQueries({ queryKey: ["signage"] })` gated by the localStorage flag `kpi.cache_purge_v22`. The flag was introduced in Phase 71 FE-02 / FE-03 to evict pre-Phase-65 cached `/api/signage/*` responses on first post-deploy visit.

**Decision (Phase 73 CACHE-03):** retain through v1.23, sunset target v1.24.

Rationale:
- The purge is one-shot per browser (localStorage gate) and adds zero runtime cost on subsequent loads.
- Removing it now would risk a stale-cache flicker on first post-deploy visit for users who have a long-lived tab open from the v1.21 era.
- One full milestone of broad adoption (v1.23) is the cautious window before deletion.
- Removal in v1.24 is tracked as backlog; the bootstrap.ts comment block names the sunset explicitly.

`frontend/src/bootstrap.ts:53-58` is intentionally outside the CACHE-02 guard scope (the guard checks `frontend/src/signage/` only) so the legacy `["signage"]` literal can persist there.

### Why no ADR?

ADR-0001 already defines the Directus/FastAPI split that motivates the namespace separation; Phase 73 is the cache-key cleanup that ADR-0001 implied but didn't fully specify. A subsection here is the right weight — full ADR ceremony would be over-engineered for a refactor with a one-shot flag-retention decision.

## How to choose: Directus vs FastAPI?

Default: Directus. A new endpoint that reads or writes a Postgres table goes through Directus unless it meets the **Compute-Justified Rubric** in [ADR-0001](./adr/0001-directus-fastapi-split.md):

1. Side effect outside Postgres (file I/O, SSE fanout, external API call, scheduler reschedule, BackgroundTask)
2. Cryptographic operation (Fernet on a column Directus must not see in plaintext)
3. Multi-row atomic compute (e.g. bulk DELETE+INSERT in one transaction)
4. Custom error contract the FE depends on

If a new compute endpoint lands in FastAPI, declare the clause in the module docstring (`Compute-justified: clause N (reason).`). The CI guard `backend/tests/test_compute_justified_rubric.py` enforces this.
