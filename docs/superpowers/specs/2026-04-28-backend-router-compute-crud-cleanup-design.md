# Backend Router Compute/CRUD Boundary Cleanup

**Date:** 2026-04-28
**Status:** Design — pending plan
**Builds on:** ADR-0001 (Directus = shape, FastAPI = compute), v1.22 backend consolidation

## Problem

Post-v1.22, FastAPI was meant to be compute-only. An audit of `backend/app/routers/` found three classes of residue:

1. **Pure-CRUD endpoints still in FastAPI** that should live in Directus.
2. **Duplicated SSE-fanout helpers** repeated across four signage admin files.
3. **Inconsistent admin-gate placement** — some routers gate at the router level, others per-route, with no written rule.

There is also no checkable rubric for whether a new endpoint belongs in FastAPI vs Directus, so drift is silent.

## Goal

Restore the v1.22 invariant cleanly and make it self-enforcing:
- Migrate four pure-CRUD endpoints to Directus.
- Consolidate four duplicated `_notify_*` helpers into `services/signage_broadcast.py`.
- Standardize auth dependency placement at the router level.
- Add ADR-0001 "compute-justified rubric" + a CI guard that fails when a FastAPI endpoint can't cite a justifying clause.

## Non-Goals

- No changes to Directus permissions for already-migrated v1.22 collections.
- No new features. No performance work.
- Sensors `community` Fernet handling stays in FastAPI (compute-justified clause 2).
- The PPTX media path stays in FastAPI (BackgroundTasks compute).

## Approach: four sequential phases

```
Phase A: signage-broadcast-helper-dedup     (pure refactor)
Phase B: admin-gate-standardization          (pure refactor + CI guard)
Phase C: directus-crud-migration-round-2     (wire surface change)
Phase D: adr-0001-compute-justified-rubric   (docs + docstrings + CI guard)
```

Sequential, not parallel. A and B don't change `/api/*` surface and the v1.22 contract-snapshot fixtures should stay green untouched. C is the only wire-affecting step and lands on a clean codebase. D ratifies the new boundary in ADR-0001 and makes it CI-enforced.

---

## Phase A — Signage broadcast helper dedup

### Current duplicates

- `signage_admin/playlists.py::_notify_playlist_changed`
- `signage_admin/playlist_items.py::_notify_playlist_changed`
- `signage_admin/media.py::_notify_media_referenced_playlists`
- `signage_admin/devices.py::_notify_device_self`

### Target API in `backend/app/services/signage_broadcast.py`

```python
async def notify_playlist_changed(
    db: AsyncSession,
    playlist_id: UUID,
    *,
    affected: list[UUID] | None = None,  # pre-computed list for delete path
    deleted: bool = False,                # uses literal etag "deleted"
) -> None: ...

async def notify_devices_for_media(db: AsyncSession, media_id: UUID) -> None: ...

async def notify_device_self(db: AsyncSession, device_id: UUID) -> None: ...
```

All three internally use `devices_affected_by_playlist`, `resolve_playlist_for_device`, and `compute_playlist_etag` from `signage_resolver.py`, plus the existing low-level `signage_broadcast.notify_device(...)`.

### Invariants to preserve

1. **Pre-commit `affected` snapshot.** The DELETE path in `playlists.py` must compute `devices_affected_by_playlist` *before* commit because tag-map cascade invalidates the query post-commit. Helper accepts `affected=` to honor this.
2. **DELETE etag literal.** Deletes broadcast `etag: "deleted"` — keep that string.
3. **Commit ordering.** All notify calls must fire after `await db.commit()` (Pitfall 3 in current docstrings). Helpers do not commit.

### Tests

- Existing SSE fanout integration tests stay green untouched (proves no behavior change).
- One unit test per helper with `signage_broadcast.notify_device` patched to a recorder, locking the payload shape.

### Commits

- `feat(A-01): introduce notify_* helpers in signage_broadcast service`
- `refactor(A-02): swap playlists.py to shared notify_playlist_changed`
- `refactor(A-03): swap playlist_items.py to shared helper`
- `refactor(A-04): swap media.py to notify_devices_for_media`
- `refactor(A-05): swap devices.py to notify_device_self`
- `chore(A-06): remove unused inline copies` (if any remain)

---

## Phase B — Admin-gate standardization

### The rule

Auth dependencies live at the router (or `APIRouter` sub-package) level. Per-route `Depends(require_admin)` is permitted only when a router mixes viewer-readable and admin-only endpoints; in that case the module docstring must declare which endpoints are admin-only.

### File alignment

| File | Current | Target |
|---|---|---|
| `uploads.py` | `get_current_user` at router; `require_admin` per-route on POST/DELETE | Split into `read_router` (viewer GET) + `admin_router` (POST/DELETE) |
| `settings.py` | Mixed (canonical mixed pattern: GETs viewer, PUT/POST admin) | No code change; add docstring declaring admin endpoints |
| `signage_admin/*` | Package-level admin gate | Already canonical |
| `sensors.py` | Router-level `[get_current_user, require_admin]` | Already canonical |
| `kpis.py`, `hr_kpis.py`, `hr_overtime.py`, `sync.py` | Audit | Most likely viewer-only; verify and align |

### CI guard

Generalize `tests/test_sensors_admin_gate.py` into `tests/test_admin_gate_audit.py`:

- Walk `app.routes`. For each `/api/*` route, assert `require_admin` appears in its dependency tree, OR the route is in an explicit allowlist of viewer/public endpoints.
- The allowlist lives in the test file as a literal set, so additions are reviewed.

### Convention doc

Append to `CLAUDE.md` Conventions section:

> Auth dependencies live at the router (or APIRouter sub-package) level. Per-route `Depends(require_admin)` is permitted only when a router mixes viewer-readable and admin-only endpoints, and the module docstring must declare which endpoints are admin-only.

### Commits

- `feat(B-01): test_admin_gate_audit walks app.routes`
- `refactor(B-02): split uploads.py into read_router + admin_router`
- `docs(B-03): add admin-endpoint declaration to settings.py docstring`
- `refactor(B-04): align kpis/hr_kpis/hr_overtime/sync gating`
- `docs(B-05): add gate convention to CLAUDE.md`

---

## Phase C — Directus CRUD migration (round 2)

### Endpoints to migrate

| Endpoint | Replacement | Permission |
|---|---|---|
| `GET /api/uploads` | Directus collection `upload_batches` | Read: Admin + Viewer |
| `GET /api/signage/media` | Directus collection `signage_media` | Read: Admin |
| `GET /api/signage/media/{id}` | Same | Read: Admin |
| `POST /api/signage/media` (non-PPTX kinds only) | Same | Create: Admin |

### Endpoints that stay (compute-justified)

- `POST /api/upload`, `DELETE /api/uploads/{id}` — parsing + cascade delete
- `PATCH /api/signage/media/{id}` — SSE fanout
- `DELETE /api/signage/media/{id}` — structured 409 + slide cleanup
- `POST /api/signage/media/pptx`, `POST /api/signage/media/{id}/reconvert` — BackgroundTasks
- All sensors endpoints — Fernet write-side; status compute
- `settings.py` PUT — APScheduler reschedule; logo upload sniffs MIME + sanitizes SVG

### Directus side

- Register `upload_batches` and `signage_media` collections (schemas already exist on shared Postgres; only Directus collection metadata + permission rules needed).
- `signage_media` LISTEN/NOTIFY trigger already wired in v1.22.
- `upload_batches` does not need fanout.

### Frontend changes

- `frontend/src/lib/api.ts::listUploads()` → Directus SDK call.
- `frontend/src/signage/lib/signageApi.ts` (existing v1.22 adapter) gains `listMedia()`, `getMedia()`, `createMedia()`. `createMedia` branches: PPTX kind keeps the existing FastAPI multipart call; all other kinds use Directus. Document the branch in the adapter.
- Errors normalized to existing `ApiErrorWithBody` contract.
- Three new contract-snapshot fixtures matching the v1.22 pattern.

### CI guards (extensions)

- OpenAPI paths snapshot: add the four migrated routes to the disallow list.
- `DB_EXCLUDE_TABLES` superset check: ensure `upload_batches` and `signage_media` are exposed by Directus.
- Phase B admin-gate audit keeps surviving routes properly gated.

### Risks and mitigations

- **Split create path for media.** FE adapter branches on `kind === 'pptx'`. Documented in the adapter file's module docstring.
- **Directus default permissions are deny-all.** Explicit role grants required; smoke test verifies a Viewer cannot read `signage_media` and an Admin can.
- **Same-origin cookies via Caddy `/directus/*`** are already in place; no new infra.

### Commits (per migration, ~5 each × 4 = ~22 total)

For each migrated endpoint: Directus collection metadata + permissions → FE adapter call → contract fixture → delete FastAPI route + tests → extend CI disallow list. Final commit: smoke-rebuild test pass.

---

## Phase D — ADR-0001 amendment + compute-justified rubric

### ADR-0001 amendment

Append to `docs/adr/0001-directus-fastapi-split.md`:

> **Compute-Justified Rubric (added v1.23):**
> A FastAPI write endpoint may read or mutate a table that Directus also exposes only if it satisfies at least one of:
> 1. **Side effect outside Postgres** (file I/O, SSE fanout, external API call, scheduler reschedule, BackgroundTask)
> 2. **Cryptographic operation** (Fernet encrypt/decrypt of a column Directus must not see in plaintext)
> 3. **Multi-row atomic compute** (e.g., bulk DELETE+INSERT in one transaction)
> 4. **Custom error contract** the FE depends on (e.g., structured `409 {detail, schedule_ids}`)
>
> Endpoints meeting none of these MUST move to Directus. New compute endpoints declare which clause justifies them in the module docstring.

### Module docstring tags

Each surviving compute module gets a one-line tag in its docstring:

```
Compute-justified: clause 1 (SSE fanout) + clause 4 (structured 409).
```

Files: `signage_admin/{playlists,playlist_items,media,devices,analytics,resolved}.py`, `sensors.py`, `settings.py`, `uploads.py`, `sync.py`, `kpis.py`, `hr_kpis.py`, `hr_overtime.py`, `signage_pair.py`, `signage_player.py`.

### CI guard: `tests/test_compute_justified_rubric.py`

- Walk `app.routes`. For each `/api/*` route, locate the source module via the route's `endpoint.__module__`.
- Assert the module's docstring contains `Compute-justified:` OR the route is in a small allowlist (viewer-only GETs that legitimately read shared tables: `settings.py` GETs, public logo).
- Allowlist is a literal set in the test file.

### Documentation companion

Add a paragraph to `docs/architecture.md` titled "How to choose: Directus vs FastAPI?" linking to the ADR rubric.

### Commits

- `docs(D-01): ADR-0001 compute-justified rubric`
- `docs(D-02): add Compute-justified tags to surviving modules` (one commit per module group: signage admin, KPIs/HR, signage device-auth, settings/uploads/sensors)
- `feat(D-03): test_compute_justified_rubric CI guard`
- `docs(D-04): architecture.md — Directus vs FastAPI section`

---

## Verification (end-state checks)

After Phase D merges:

- `docker compose exec api pytest` green, including new audit + rubric tests.
- `./scripts/smoke-rebuild.sh` exits 0.
- `npm run build` exits 0 with zero `error TS`.
- OpenAPI paths snapshot contains zero of the four migrated routes.
- Each surviving `/api/*` module either has a `Compute-justified:` docstring tag or is in the audited viewer/public allowlist.
- ADR-0001 documents the rubric.

## Out of scope / explicitly deferred

- Sensors `GET /api/sensors` and `GET /api/sensors/{id}/readings` migration — possible future round once Directus permissions can hide the encrypted `community` column reliably.
- Refactoring `sensors.py` `hours` validation to `Annotated[Query]` — cosmetic, separate ticket.
