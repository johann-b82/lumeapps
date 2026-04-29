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
| `/`          | `frontend:5173`   | Preserved                    | Admin SPA (login, launcher, dashboards, signage admin).                    |
| `/api/*`     | `api:8000`        | Preserved                    | FastAPI routes live at `/api/...`. SSE passthrough via `flush_interval -1` + 24h `read_timeout`. |
| `/directus/*`| `directus:8055`   | **Stripped** (`handle_path`) | Directus doesn't know it's behind a subpath; it expects bare `/auth`, `/items`, `/assets`, `/server`. |
| `/player/*`  | `frontend:5173`   | Preserved                    | Kiosk bundle. Vite dev serves `/player/` as a separate entry; prod build writes to `dist/player/`. |

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

**Verification:** `scripts/verify-phase-64-proxy.sh` smoke-tests the four
routes plus a 65-second hold probe that asserts the proxy does not close
long-lived connections. Run it after any compose or Caddyfile change.

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
