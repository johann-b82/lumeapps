# ADR-0001: Directus / FastAPI Split

**Status:** Accepted
**Date:** 2026-04-25
**Milestone:** v1.22 — Backend Consolidation

## Context

Through milestones v1.0–v1.21, kpi-dashboard accumulated ~25 pure-CRUD
FastAPI endpoints for signage admin, sales/employee row lookups, and
auth identity. Each endpoint duplicated logic Directus 11 already
provides natively (filtering, validation, RBAC, REST shape). The
duplication slowed feature work and created a second source of truth
for collection schemas already defined in Alembic.

v1.22 set out to eliminate this duplication while preserving the
compute-shaped surface (file parsing, KPI aggregation, SSE bridge,
APScheduler jobs, JWT minting) that Directus cannot express.

## Decision

**Directus = shape. FastAPI = compute.**

Specifically:

- **Directus owns:** CRUD on `sales_records`, `personio_employees`,
  `signage_devices`, `signage_playlists`, `signage_playlist_items`,
  `signage_device_tags`, `signage_playlist_tag_map`, `signage_device_tag_map`,
  `signage_schedules`. Identity reads via `readMe()`.
- **FastAPI owns:** Upload POST + file parsing, KPI compute endpoints,
  Personio + sensor sync (APScheduler), `signage_player` SSE bridge +
  envelope, `signage_pair` JWT minting, media + PPTX (`/api/signage/media*`),
  calibration PATCH (`/api/signage/devices/{id}/calibration`),
  `GET /api/signage/resolved/{id}` (compute-shaped resolver), `DELETE
  /api/signage/playlists/{id}` (preserves structured 409 shape), bulk
  `PUT /api/signage/playlists/{id}/items` (atomic DELETE+INSERT), and
  `GET /api/signage/analytics/devices` (bucketed uptime aggregate).
- **Alembic remains the sole DDL owner** of `public.*` tables.
  Directus owns metadata rows only.
- **SSE bridge:** Postgres `LISTEN/NOTIFY` (Option A) — Alembic-owned
  triggers, FastAPI lifespan-hosted asyncpg listener. Single-listener
  invariant via `--workers 1`.
- **Frontend adapter seam:** `signageApi.ts` wraps Directus SDK calls
  and returns the same shapes existing TanStack Query consumers
  expect; `toApiError()` normalizes Directus plain-object errors to
  `ApiErrorWithBody`.
- **Cache-key namespaces:** `['directus', <collection>, ...]` and
  `['fastapi', <topic>, ...]` are the canonical patterns. Legacy
  `signageKeys.*` coexists for un-migrated reads (media, analytics).

## Consequences

**Positive:**
- One source of truth per concern. Schema lives in Alembic; CRUD in
  Directus; compute in FastAPI.
- Adding new collections requires only an Alembic migration + a
  Directus snapshot YAML edit. No FastAPI router boilerplate.
- Per-collection field allowlists in `bootstrap-roles.sh` make Viewer
  RBAC explicit and auditable.

**Negative / tradeoffs:**
- Composite-PK Directus collections (`signage_playlist_tag_map`,
  `signage_device_tag_map`) registered with `schema:null` return 403
  to admin REST queries — known Directus limitation. Worked around
  with FE-driven tag-map diff (Phase 69 D-02).
- Directus version drift could break adapter contracts. Mitigated by
  contract-snapshot tests (`frontend/src/tests/contracts/*.json`,
  Phase 71 FE-05).
- Two error-throwing transports in the FE (Directus plain objects,
  FastAPI plain `Error`). Mitigated by central `toApiError()` helper.

**Deferred / not decided:**
- **Settings rewrite to Directus** — deferred. The oklch/hex validators
  + SVG sanitization + ETag + logo BYTEA surface is too custom for a
  clean Directus-hook port today. Settings remains a deferred decision,
  revisited per-milestone.

## Alternatives Considered

- **Full Directus** (move every endpoint including compute) — rejected
  because Directus aggregations cannot express bucketed uptime, and
  Python tooling for APScheduler / Personio / SNMP / PPTX is
  stronger than Directus Flows.
- **Full FastAPI** (status quo) — rejected because the duplication
  cost was the trigger for v1.22 in the first place.
- **Directus Flow webhooks for SSE** — rejected in favor of Postgres
  `LISTEN/NOTIFY` (Option A) for writer-agnostic fan-out (fires on
  Directus, psql, future writers).

## References

- `.planning/REQUIREMENTS.md` — v1.22 requirements
- `.planning/ROADMAP.md` — milestone phasing
- `docs/architecture.md` — current architecture diagram + boundary section
- `docs/operator-runbook.md` `## v1.22 Rollback Procedure` — rollback steps
