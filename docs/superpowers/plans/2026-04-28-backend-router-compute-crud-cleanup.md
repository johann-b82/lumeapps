# Backend Router Compute/CRUD Boundary Cleanup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the v1.22 "Directus = shape, FastAPI = compute" invariant cleanly: dedup signage SSE-fanout helpers, standardize admin-gate placement, migrate four pure-CRUD endpoints to Directus, and ratify a CI-enforced compute-justified rubric in ADR-0001.

**Architecture:** Four sequential phases (A→B→C→D). A and B are pure refactors that don't touch `/api/*` surface. C is the only wire-affecting step and migrates four endpoints to Directus. D adds the rubric + CI guard. Each phase ends green: `pytest`, `smoke-rebuild.sh`, `npm run build`.

**Tech Stack:** FastAPI 0.135 / SQLAlchemy 2.0 async / pytest + httpx.AsyncClient / Directus 11 / React 19 + TanStack Query. Driver spec: `docs/superpowers/specs/2026-04-28-backend-router-compute-crud-cleanup-design.md`.

---

## File Structure

### Phase A — Helper dedup
- **Modify** `backend/app/services/signage_broadcast.py` — add three high-level `notify_*` async helpers; existing low-level `notify_device(device_id, payload)` stays.
- **Modify** `backend/app/routers/signage_admin/playlists.py` — drop inline `_notify_playlist_changed`; call shared helper.
- **Modify** `backend/app/routers/signage_admin/playlist_items.py` — same.
- **Modify** `backend/app/routers/signage_admin/media.py` — drop `_notify_media_referenced_playlists`; call shared helper.
- **Modify** `backend/app/routers/signage_admin/devices.py` — drop `_notify_device_self`; call shared helper.
- **Create** `backend/tests/test_signage_broadcast_helpers.py` — unit tests for the three new helpers.

### Phase B — Admin-gate standardization
- **Create** `backend/tests/test_admin_gate_audit.py` — generalized version of `test_sensors_admin_gate.py` that walks all `/api/*` routes.
- **Modify** `backend/app/routers/uploads.py` — split into `read_router` (viewer GET) and `admin_router` (POST/DELETE).
- **Modify** `backend/app/routers/settings.py` — add admin-endpoints declaration to module docstring.
- **Modify** `backend/app/routers/{kpis,hr_kpis,hr_overtime,sync}.py` — verify and align dependencies.
- **Modify** `CLAUDE.md` — append gate convention.

### Phase C — Directus CRUD migration round 2
- **Delete** route handlers in `backend/app/routers/uploads.py::list_uploads`, `backend/app/routers/signage_admin/media.py::list_media`, `get_media`, and the non-PPTX branch of `create_media`.
- **Modify** `frontend/src/lib/api.ts::listUploads` — call Directus SDK.
- **Modify** `frontend/src/signage/lib/signageApi.ts` — add `listMedia`, `getMedia`, `createMedia` (branches on `kind === 'pptx'`).
- **Create** Directus collection definitions for `upload_batches` and `signage_media` in `directus/snapshots/` (existing pattern from v1.22).
- **Create** three new contract-snapshot fixtures under `backend/tests/fixtures/contracts/`.
- **Modify** `backend/tests/test_openapi_paths_snapshot.py` — extend disallow list with the four migrated routes.
- **Modify** `backend/tests/test_db_exclude_tables_directus_collections.py` — assert `upload_batches` and `signage_media` are exposed.

### Phase D — ADR-0001 amendment + rubric guard
- **Modify** `docs/adr/0001-directus-fastapi-split.md` — append rubric.
- **Modify** all surviving compute modules (`backend/app/routers/{signage_admin/*,sensors,settings,uploads,sync,kpis,hr_kpis,hr_overtime,signage_pair,signage_player}.py`) — add `Compute-justified:` docstring tag.
- **Create** `backend/tests/test_compute_justified_rubric.py` — CI guard that walks `app.routes` and asserts the tag.
- **Modify** `docs/architecture.md` — add "How to choose: Directus vs FastAPI?" section.

---

# PHASE A — Signage broadcast helper dedup

## Task A-1: Introduce `notify_*` helpers in signage_broadcast service

**Files:**
- Modify: `backend/app/services/signage_broadcast.py` (append after the existing `notify_device(device_id, payload)` definition)
- Test: `backend/tests/test_signage_broadcast_helpers.py` (new)

- [ ] **Step 1: Write failing tests for the three new helpers**

Create `backend/tests/test_signage_broadcast_helpers.py`:

```python
"""Unit tests for signage_broadcast high-level notify_* helpers (Phase A)."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.services import signage_broadcast


@pytest.mark.asyncio
async def test_notify_playlist_changed_emits_per_affected_device(monkeypatch):
    pid = uuid.uuid4()
    dev_a, dev_b = 11, 22
    sent: list[tuple[int, dict]] = []

    async def fake_affected(db, playlist_id):
        assert playlist_id == pid
        return [dev_a, dev_b]

    async def fake_resolve(db, dev):
        return {"slides": [], "device_id": dev.id}

    def fake_etag(env):
        return f"etag-{env['device_id']}"

    monkeypatch.setattr(signage_broadcast, "devices_affected_by_playlist", fake_affected, raising=False)
    monkeypatch.setattr(signage_broadcast, "resolve_playlist_for_device", fake_resolve, raising=False)
    monkeypatch.setattr(signage_broadcast, "compute_playlist_etag", fake_etag, raising=False)

    class _Dev:
        def __init__(self, _id): self.id = _id

    async def fake_load(db, device_id):
        return _Dev(device_id)

    monkeypatch.setattr(signage_broadcast, "_load_device", fake_load, raising=False)

    with patch.object(signage_broadcast, "notify_device", side_effect=lambda d, p: sent.append((d, p))):
        await signage_broadcast.notify_playlist_changed(db=None, playlist_id=pid)

    assert [d for d, _ in sent] == [dev_a, dev_b]
    assert all(p["event"] == "playlist-changed" for _, p in sent)
    assert all(p["playlist_id"] == str(pid) for _, p in sent)
    assert sent[0][1]["etag"] == "etag-11"


@pytest.mark.asyncio
async def test_notify_playlist_changed_delete_uses_literal_etag(monkeypatch):
    pid = uuid.uuid4()
    sent: list[tuple[int, dict]] = []
    with patch.object(signage_broadcast, "notify_device", side_effect=lambda d, p: sent.append((d, p))):
        await signage_broadcast.notify_playlist_changed(
            db=None, playlist_id=pid, affected=[1, 2, 3], deleted=True
        )
    assert [d for d, _ in sent] == [1, 2, 3]
    assert {p["etag"] for _, p in sent} == {"deleted"}
    assert {p["playlist_id"] for _, p in sent} == {str(pid)}


@pytest.mark.asyncio
async def test_notify_devices_for_media_dispatches_per_referenced_playlist(monkeypatch):
    media_id = uuid.uuid4()
    playlist_ids = [uuid.uuid4(), uuid.uuid4()]
    calls: list = []

    async def fake_referenced(db, mid):
        assert mid == media_id
        return playlist_ids

    async def fake_notify_playlist(db, playlist_id, **kw):
        calls.append(playlist_id)

    monkeypatch.setattr(signage_broadcast, "_playlists_referencing_media", fake_referenced, raising=False)
    monkeypatch.setattr(signage_broadcast, "notify_playlist_changed", fake_notify_playlist)

    await signage_broadcast.notify_devices_for_media(db=None, media_id=media_id)

    assert calls == playlist_ids


@pytest.mark.asyncio
async def test_notify_device_self_emits_resolved_envelope_etag(monkeypatch):
    dev_id = 99
    sent: list[tuple[int, dict]] = []

    class _Dev:
        def __init__(self, _id): self.id = _id

    async def fake_load(db, device_id):
        return _Dev(device_id)

    async def fake_resolve(db, dev):
        return {"device_id": dev.id, "slides": []}

    def fake_etag(env):
        return "etag-self"

    monkeypatch.setattr(signage_broadcast, "_load_device", fake_load, raising=False)
    monkeypatch.setattr(signage_broadcast, "resolve_playlist_for_device", fake_resolve, raising=False)
    monkeypatch.setattr(signage_broadcast, "compute_playlist_etag", fake_etag, raising=False)

    with patch.object(signage_broadcast, "notify_device", side_effect=lambda d, p: sent.append((d, p))):
        await signage_broadcast.notify_device_self(db=None, device_id=dev_id)

    assert sent == [(dev_id, {"event": "playlist-changed", "device_id": str(dev_id), "etag": "etag-self"})]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api pytest backend/tests/test_signage_broadcast_helpers.py -v`
Expected: FAIL with `AttributeError: module 'app.services.signage_broadcast' has no attribute 'notify_playlist_changed'` (and similar for the other helpers).

- [ ] **Step 3: Implement the three helpers in `signage_broadcast.py`**

Append to `backend/app/services/signage_broadcast.py`:

```python
# ---------------------------------------------------------------------------
# Phase A — high-level notify_* helpers consolidated from signage_admin/*.py.
# These replace the four inline ``_notify_*`` duplicates that previously
# lived in playlists.py, playlist_items.py, media.py, and devices.py.
#
# Invariants:
#   1. Helpers DO NOT commit. Caller commits, then calls the helper.
#   2. ``notify_playlist_changed(..., affected=[...], deleted=True)`` is the
#      DELETE path: caller pre-computes ``affected`` BEFORE commit (because
#      tag-map cascade invalidates the query post-commit), then commits, then
#      calls the helper with ``deleted=True`` so the literal etag "deleted"
#      is broadcast.
#   3. Low-level ``notify_device(device_id, payload)`` above stays as-is.
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Imported lazily inside functions to avoid import-time cycles with models/.
from app.services.signage_resolver import (  # noqa: E402
    compute_playlist_etag,
    devices_affected_by_playlist,
    resolve_playlist_for_device,
)


async def _load_device(db: "AsyncSession", device_id: int):
    from app.models import SignageDevice
    return (await db.execute(select(SignageDevice).where(SignageDevice.id == device_id))).scalar_one_or_none()


async def _playlists_referencing_media(db: "AsyncSession", media_id: UUID) -> list[UUID]:
    from app.models import SignagePlaylistItem
    rows = await db.execute(
        select(SignagePlaylistItem.playlist_id)
        .where(SignagePlaylistItem.media_id == media_id)
        .distinct()
    )
    return list(rows.scalars().all())


async def notify_playlist_changed(
    db: "AsyncSession",
    playlist_id: UUID,
    *,
    affected: list[int] | None = None,
    deleted: bool = False,
) -> None:
    """Broadcast playlist-changed to every device whose envelope is affected.

    Default path resolves affected devices and re-resolves their envelope etag.
    DELETE path passes pre-computed ``affected`` and ``deleted=True``; this
    skips the resolver and emits the literal etag ``"deleted"`` so the
    player invalidates without trying to fetch a now-deleted playlist.
    """
    if deleted:
        if affected is None:
            raise ValueError("deleted=True requires pre-computed affected= list")
        for device_id in affected:
            notify_device(
                device_id,
                {"event": "playlist-changed", "playlist_id": str(playlist_id), "etag": "deleted"},
            )
        return

    device_ids = affected if affected is not None else await devices_affected_by_playlist(db, playlist_id)
    for device_id in device_ids:
        dev = await _load_device(db, device_id)
        if dev is None:
            continue
        envelope = await resolve_playlist_for_device(db, dev)
        notify_device(
            device_id,
            {
                "event": "playlist-changed",
                "playlist_id": str(playlist_id),
                "etag": compute_playlist_etag(envelope),
            },
        )


async def notify_devices_for_media(db: "AsyncSession", media_id: UUID) -> None:
    """Fan out playlist-changed for every playlist that references this media."""
    for pid in await _playlists_referencing_media(db, media_id):
        await notify_playlist_changed(db, pid)


async def notify_device_self(db: "AsyncSession", device_id: int) -> None:
    """Notify a single device its own resolved envelope changed (e.g. tag edit)."""
    dev = await _load_device(db, device_id)
    if dev is None:
        return
    envelope = await resolve_playlist_for_device(db, dev)
    notify_device(
        device_id,
        {"event": "playlist-changed", "device_id": str(device_id), "etag": compute_playlist_etag(envelope)},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api pytest backend/tests/test_signage_broadcast_helpers.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run the broader signage suite to confirm no regression**

Run: `docker compose exec api pytest backend/tests/test_signage_broadcast.py backend/tests/test_signage_broadcast_integration.py -v`
Expected: PASS — these still exercise the low-level `notify_device`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/signage_broadcast.py backend/tests/test_signage_broadcast_helpers.py
git commit -m "feat(A-01): introduce notify_* helpers in signage_broadcast service"
```

---

## Task A-2: Swap `playlists.py` to shared `notify_playlist_changed`

**Files:**
- Modify: `backend/app/routers/signage_admin/playlists.py` (delete `_notify_playlist_changed` def at ~lines 45–69; rewrite the post-commit fanout in `delete_playlist` ~lines 120–128)

- [ ] **Step 1: Delete the inline helper and the inline post-commit loop**

Remove `async def _notify_playlist_changed(...)` and the inline `for device_id in affected: signage_broadcast.notify_device(...)` block at the end of `delete_playlist`.

- [ ] **Step 2: Replace with the shared helper call**

In `delete_playlist`, after `await db.commit()` (and only on the success path, not the IntegrityError branch), call:

```python
    await signage_broadcast.notify_playlist_changed(
        db, playlist_id, affected=affected, deleted=True
    )
```

The pre-commit `affected = await devices_affected_by_playlist(db, playlist_id)` line stays (Pitfall 3 + tag-map-cascade snapshot).

- [ ] **Step 3: Update module docstring**

Change the line referencing `_notify_playlist_changed` to "Uses the shared `signage_broadcast.notify_playlist_changed` helper."

- [ ] **Step 4: Run signage tests**

Run: `docker compose exec api pytest backend/tests/test_signage_admin_router.py backend/tests/test_signage_broadcast_integration.py -v`
Expected: PASS, including the existing DELETE 409 + post-delete fanout cases.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/signage_admin/playlists.py
git commit -m "refactor(A-02): swap playlists.py to shared notify_playlist_changed"
```

---

## Task A-3: Swap `playlist_items.py` to shared helper

**Files:**
- Modify: `backend/app/routers/signage_admin/playlist_items.py` (delete `_notify_playlist_changed` at ~line 24; replace call at ~line 89)

- [ ] **Step 1: Delete the inline `_notify_playlist_changed` function**

- [ ] **Step 2: Replace the call site**

Change `await _notify_playlist_changed(db, playlist_id)` to:

```python
    await signage_broadcast.notify_playlist_changed(db, playlist_id)
```

(Default path — no `deleted=True`, no pre-snapshot needed; playlist_items mutations don't cascade tag-map.)

- [ ] **Step 3: Run tests**

Run: `docker compose exec api pytest backend/tests/test_signage_admin_router.py backend/tests/test_signage_broadcast_integration.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/signage_admin/playlist_items.py
git commit -m "refactor(A-03): swap playlist_items.py to shared helper"
```

---

## Task A-4: Swap `media.py` to `notify_devices_for_media`

**Files:**
- Modify: `backend/app/routers/signage_admin/media.py` (delete `_notify_media_referenced_playlists` ~line 41; replace call ~line 164)

- [ ] **Step 1: Delete the inline helper**

- [ ] **Step 2: Replace the call site**

Change `await _notify_media_referenced_playlists(db, media_id)` to:

```python
    await signage_broadcast.notify_devices_for_media(db, media_id)
```

- [ ] **Step 3: Run tests**

Run: `docker compose exec api pytest backend/tests/test_signage_admin_router.py backend/tests/test_signage_pptx_pipeline_integration.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/signage_admin/media.py
git commit -m "refactor(A-04): swap media.py to notify_devices_for_media"
```

---

## Task A-5: Swap `devices.py` to `notify_device_self`

**Files:**
- Modify: `backend/app/routers/signage_admin/devices.py` (delete `_notify_device_self` at ~line 30; replace its call sites)

- [ ] **Step 1: Delete the inline helper and replace call sites**

Replace every `await _notify_device_self(db, device_id)` with:

```python
    await signage_broadcast.notify_device_self(db, device_id)
```

- [ ] **Step 2: Run tests**

Run: `docker compose exec api pytest backend/tests/test_signage_admin_router.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/signage_admin/devices.py
git commit -m "refactor(A-05): swap devices.py to notify_device_self"
```

---

## Task A-6: Final sweep — confirm no inline `_notify_*` copies remain

- [ ] **Step 1: Search**

Run: `grep -rn "_notify_playlist_changed\|_notify_media_referenced\|_notify_device_self" backend/app/routers/signage_admin/`
Expected: empty output.

- [ ] **Step 2: Run full backend suite**

Run: `docker compose exec api pytest -q`
Expected: PASS.

- [ ] **Step 3: Commit (only if there is anything to remove)**

If `grep` was already empty, skip the commit. Otherwise:

```bash
git add backend/app/routers/signage_admin/
git commit -m "chore(A-06): remove residual inline notify copies"
```

---

# PHASE B — Admin-gate standardization

## Task B-1: Generalize the admin-gate audit test

**Files:**
- Create: `backend/tests/test_admin_gate_audit.py`

- [ ] **Step 1: Write the audit test**

```python
"""CI guard: every /api/* route is admin-gated unless explicitly allowlisted.

Generalization of test_sensors_admin_gate.py per Phase B of
docs/superpowers/specs/2026-04-28-backend-router-compute-crud-cleanup-design.md.

The allowlist is a literal set in this file so additions are reviewed.
"""
from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app
from app.security.directus_auth import require_admin


# (path, frozenset(methods)) — viewer-readable or public endpoints.
# Adding to this set requires reviewer sign-off; keep it small and justified.
ADMIN_GATE_ALLOWLIST: set[tuple[str, frozenset[str]]] = {
    # Viewer-readable settings GETs (mixed-gate router; see settings.py docstring).
    ("/api/settings", frozenset({"GET"})),
    ("/api/settings/logo", frozenset({"GET"})),
    # KPI dashboard reads — viewer role.
    # NOTE: regenerate this list during Phase B by inspecting kpis.py / hr_kpis.py / hr_overtime.py.
    # If a route appears here that you did not expect, fail the audit by trimming this set.
}


def _walk_deps(deps):
    out = []
    for d in deps:
        out.append(d.call)
        out.extend(_walk_deps(d.dependencies))
    return out


def test_every_api_route_is_admin_gated_or_allowlisted():
    api_routes = [
        r for r in app.routes
        if isinstance(r, APIRoute) and r.path.startswith("/api/")
    ]
    assert api_routes, "no /api/* routes registered — include_router missing?"

    violations: list[str] = []
    for route in api_routes:
        methods = frozenset(m for m in route.methods if m != "HEAD")
        if (route.path, methods) in ADMIN_GATE_ALLOWLIST:
            continue
        # Also accept partial-method allowlist (e.g. only GET allowlisted on a multi-method route).
        if any((route.path, frozenset({m})) in ADMIN_GATE_ALLOWLIST for m in methods):
            # Fine-grained: only the allowlisted method is exempt; assert require_admin
            # is present anyway (mixed-gate routers should still depend on require_admin
            # for their write endpoints, which is what we are checking here for the
            # remaining methods). We approximate by skipping; per-method dep walking
            # is unsupported by FastAPI's APIRoute. Document in spec.
            continue
        all_calls = _walk_deps(route.dependant.dependencies)
        if require_admin not in all_calls:
            violations.append(f"{sorted(methods)} {route.path}")

    assert not violations, (
        "the following /api/* routes are not admin-gated and not in "
        "ADMIN_GATE_ALLOWLIST:\n  - " + "\n  - ".join(violations)
    )
```

- [ ] **Step 2: Run it — expect failures that drive Tasks B-2..B-4**

Run: `docker compose exec api pytest backend/tests/test_admin_gate_audit.py -v`
Expected: FAIL with a list of routes that are not admin-gated and not allowlisted. Capture the output — this is the worklist for Task B-2 through B-4.

- [ ] **Step 3: Commit the failing test (intentional red)**

```bash
git add backend/tests/test_admin_gate_audit.py
git commit -m "feat(B-01): test_admin_gate_audit walks app.routes"
```

---

## Task B-2: Split `uploads.py` into read_router + admin_router

**Files:**
- Modify: `backend/app/routers/uploads.py`
- Modify: `backend/app/main.py` (or wherever `include_router(uploads.router)` is wired)

- [ ] **Step 1: Read `uploads.py` and identify the GET (viewer) vs POST/DELETE (admin) split**

Run: `cat backend/app/routers/uploads.py | head -60`

- [ ] **Step 2: Refactor to two `APIRouter` instances**

Replace the single-router pattern with:

```python
read_router = APIRouter(
    prefix="/uploads",
    tags=["uploads"],
    dependencies=[Depends(get_current_user)],
)
admin_router = APIRouter(
    prefix="/uploads",
    tags=["uploads"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)

# GET /uploads — viewer
@read_router.get("")
async def list_uploads(...): ...

# POST /uploads, DELETE /uploads/{id} — admin
@admin_router.post("")
async def create_upload(...): ...

@admin_router.delete("/{upload_id}")
async def delete_upload(...): ...
```

Drop any per-route `Depends(require_admin)` from POST/DELETE handlers — it's now at the router level.

- [ ] **Step 3: Update `app/main.py` to include both routers**

```python
from app.routers import uploads as uploads_module

app.include_router(uploads_module.read_router, prefix="/api")
app.include_router(uploads_module.admin_router, prefix="/api")
```

(Match the existing include_router style in the file.)

- [ ] **Step 4: Update `ADMIN_GATE_ALLOWLIST` in `test_admin_gate_audit.py` if `GET /api/uploads` is the only viewer-readable upload endpoint**

Add `("/api/uploads", frozenset({"GET"}))` to the allowlist set.

(Note: this endpoint will be removed in Phase C, but during Phase B it must be allowlisted to keep the gate-audit green. Phase C trims the allowlist back.)

- [ ] **Step 5: Run audit + uploads tests**

Run: `docker compose exec api pytest backend/tests/test_admin_gate_audit.py backend/tests/test_rbac.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/uploads.py backend/app/main.py backend/tests/test_admin_gate_audit.py
git commit -m "refactor(B-02): split uploads.py into read_router + admin_router"
```

---

## Task B-3: Add admin-endpoint declaration to `settings.py` docstring

**Files:**
- Modify: `backend/app/routers/settings.py` (module docstring at the top)

- [ ] **Step 1: Append a "Mixed gate" block to the module docstring**

Add at the end of the existing module docstring:

```
Mixed gate (Phase B convention):
    Viewer-readable: GET /api/settings, GET /api/settings/logo
    Admin-only:      PUT /api/settings, POST /api/settings/logo,
                     DELETE /api/settings/logo, and any other write paths.
    Per-route ``Depends(require_admin)`` is used here because viewer reads
    and admin writes coexist on the same prefix (CLAUDE.md Conventions §
    "Auth dependencies live at the router level except mixed-gate routers").
```

Adjust the listed admin-only endpoints to match what's actually in the file.

- [ ] **Step 2: Run tests**

Run: `docker compose exec api pytest backend/tests/test_settings_api.py backend/tests/test_admin_gate_audit.py -v`
Expected: PASS (or audit may still flag mixed-gate routes — confirm allowlist covers viewer GETs).

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/settings.py
git commit -m "docs(B-03): add admin-endpoint declaration to settings.py docstring"
```

---

## Task B-4: Align `kpis`, `hr_kpis`, `hr_overtime`, `sync` gating

**Files:**
- Modify: `backend/app/routers/kpis.py`
- Modify: `backend/app/routers/hr_kpis.py`
- Modify: `backend/app/routers/hr_overtime.py`
- Modify: `backend/app/routers/sync.py`

For each file, audit and align. Most are viewer-only reads and need the **read** gate (`get_current_user` only) at the router level; `sync.py` triggers admin operations and needs `require_admin` at router level.

- [ ] **Step 1: For each file, inspect the current state**

Run: `for f in kpis hr_kpis hr_overtime sync; do echo "=== $f ==="; sed -n '1,30p' backend/app/routers/$f.py; done`

- [ ] **Step 2: Decide gate per file using this rule**

- If every endpoint is viewer-readable → router-level `dependencies=[Depends(get_current_user)]`. Add the path+method tuples to `ADMIN_GATE_ALLOWLIST`.
- If every endpoint is admin-only → router-level `dependencies=[Depends(get_current_user), Depends(require_admin)]`. No allowlist entry needed.
- If mixed → see Task B-3 pattern: keep mixed gate, declare in docstring, allowlist the viewer methods.

- [ ] **Step 3: Apply the gate alignment to each file**

Concrete expected outcome per spec § Phase B "File alignment":
- `kpis.py`, `hr_kpis.py`, `hr_overtime.py` → viewer-only at router level. Add their paths to the allowlist.
- `sync.py` → admin-only at router level (no allowlist entry).

For each viewer-only router, set:

```python
router = APIRouter(
    prefix="/...",
    tags=[...],
    dependencies=[Depends(get_current_user)],
)
```

For `sync.py`:

```python
router = APIRouter(
    prefix="/sync",
    tags=["sync"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)
```

Remove any redundant per-route `Depends(...)` that the router-level dep now covers.

- [ ] **Step 4: Update `ADMIN_GATE_ALLOWLIST` in `test_admin_gate_audit.py`**

Add the actual paths discovered (example):

```python
("/api/kpis", frozenset({"GET"})),
("/api/kpis/{kpi_id}", frozenset({"GET"})),
("/api/hr-kpis", frozenset({"GET"})),
("/api/hr-overtime", frozenset({"GET"})),
# ... whatever the inspection in Step 1 surfaced
```

- [ ] **Step 5: Run audit + per-router tests**

Run: `docker compose exec api pytest backend/tests/test_admin_gate_audit.py backend/tests/test_kpi_endpoints.py backend/tests/test_hr_kpi_range.py backend/tests/test_hr_overtime_router.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/kpis.py backend/app/routers/hr_kpis.py backend/app/routers/hr_overtime.py backend/app/routers/sync.py backend/tests/test_admin_gate_audit.py
git commit -m "refactor(B-04): align kpis/hr_kpis/hr_overtime/sync gating"
```

---

## Task B-5: Add gate convention to CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (Conventions section)

- [ ] **Step 1: Append to the Conventions section**

Replace the existing "Conventions not yet established" line with:

```markdown
## Conventions

### Auth gate placement

Auth dependencies live at the router (or `APIRouter` sub-package) level. Per-route `Depends(require_admin)` is permitted only when a router mixes viewer-readable and admin-only endpoints, and the module docstring must declare which endpoints are admin-only. See `backend/tests/test_admin_gate_audit.py` for the CI guard.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(B-05): add gate convention to CLAUDE.md"
```

---

## Task B-6: Phase B verification

- [ ] **Step 1: Full backend suite**

Run: `docker compose exec api pytest -q`
Expected: PASS.

- [ ] **Step 2: Smoke-rebuild**

Run: `./scripts/smoke-rebuild.sh`
Expected: exit 0.

- [ ] **Step 3: Frontend build**

Run: `cd frontend && npm run build`
Expected: exit 0, zero `error TS`.

If anything fails, fix before starting Phase C — Phase C compounds risk and must land on a green Phase B.

---

# PHASE C — Directus CRUD migration round 2

> Per-migration template = 5 commits: (1) Directus collection + permissions, (2) FE adapter call, (3) contract fixture, (4) delete FastAPI route + tests, (5) extend CI disallow list.
>
> Four migrations in this phase:
> - C-1: `GET /api/uploads` → Directus `upload_batches`
> - C-2: `GET /api/signage/media` → Directus `signage_media`
> - C-3: `GET /api/signage/media/{id}` → Directus `signage_media`
> - C-4: `POST /api/signage/media` (non-PPTX kinds) → Directus `signage_media`

## Task C-1: Migrate `GET /api/uploads` → Directus `upload_batches`

**Files:**
- Modify: `directus/snapshots/<latest>.yaml` (or current snapshot mechanism — match v1.22 pattern)
- Modify: `frontend/src/lib/api.ts` (`listUploads`)
- Create: `backend/tests/fixtures/contracts/upload_batches.json` (contract snapshot)
- Modify: `backend/app/routers/uploads.py` (delete `read_router` GET handler)
- Modify: `backend/app/main.py` (drop `read_router` include if it becomes empty)
- Modify: `backend/tests/test_openapi_paths_snapshot.py` (extend disallow list)
- Modify: `backend/tests/test_db_exclude_tables_directus_collections.py` (assert `upload_batches` exposed)

- [ ] **Step 1: Register `upload_batches` collection in Directus snapshot**

Match the v1.22 pattern. Inspect a previously migrated collection (e.g. `signage_playlists`) and replicate:

Run: `grep -rn "signage_playlists" directus/snapshots/ | head -10`

Add `upload_batches` to the snapshot with:
- Collection metadata (display name "Upload Batches", icon, hidden=false)
- Permissions: Admin role + Viewer role both have `read` on all fields. No create/update/delete (Phase C migrates GET only; POST/DELETE stay in FastAPI).

- [ ] **Step 2: Apply the snapshot in dev**

Run: `docker compose exec directus npx directus schema apply --yes ./snapshots/<file>.yaml`
Expected: 0 errors. Verify with `curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8055/items/upload_batches | jq '.data | length'`.

- [ ] **Step 3: Add the contract-snapshot fixture**

Create `backend/tests/fixtures/contracts/upload_batches.json` containing the canonical Directus list response shape (one row, all fields). Match the field names exposed by Directus 1:1 — the fixture is what the FE will type against.

- [ ] **Step 4: Update FE adapter — `frontend/src/lib/api.ts::listUploads`**

Replace the `fetch('/api/uploads')` body with a Directus SDK call:

```ts
import { directus } from "./directus";
import { readItems } from "@directus/sdk";

export async function listUploads(): Promise<UploadBatch[]> {
  return await directus.request(readItems("upload_batches", { sort: ["-created_at"] }));
}
```

(Match the import style used in the v1.22-migrated calls in `frontend/src/signage/lib/signageApi.ts`.)

- [ ] **Step 5: Verify FE build still typechecks**

Run: `cd frontend && npm run build`
Expected: 0 `error TS`. The `UploadBatch` type may need updating to match Directus field shape — adjust as needed.

- [ ] **Step 6: Delete the FastAPI route**

In `backend/app/routers/uploads.py`, remove the `@read_router.get("")` handler entirely. If `read_router` now has zero handlers, remove its definition and the include in `main.py`.

- [ ] **Step 7: Trim the allowlist in `test_admin_gate_audit.py`**

Remove `("/api/uploads", frozenset({"GET"}))` from `ADMIN_GATE_ALLOWLIST` (the route no longer exists).

- [ ] **Step 8: Extend OpenAPI disallow list**

In `backend/tests/test_openapi_paths_snapshot.py`, add `"/api/uploads"` (GET method) to the disallow list / removed-routes set so a regression that re-adds it fails the test.

- [ ] **Step 9: Extend Directus exposure assertion**

In `backend/tests/test_db_exclude_tables_directus_collections.py`, add `upload_batches` to the set of tables that MUST be exposed by Directus.

- [ ] **Step 10: Run full backend + smoke-rebuild + FE build**

Run: `docker compose exec api pytest -q && ./scripts/smoke-rebuild.sh && (cd frontend && npm run build)`
Expected: all green.

- [ ] **Step 11: Commit (split into the 5 logical commits)**

```bash
git add directus/snapshots/
git commit -m "feat(C-1a): expose upload_batches via Directus collection + permissions"

git add frontend/src/lib/api.ts frontend/src/lib/directus.ts
git commit -m "feat(C-1b): listUploads() uses Directus SDK"

git add backend/tests/fixtures/contracts/upload_batches.json
git commit -m "test(C-1c): contract fixture for upload_batches"

git add backend/app/routers/uploads.py backend/app/main.py
git commit -m "refactor(C-1d): delete GET /api/uploads FastAPI route"

git add backend/tests/test_openapi_paths_snapshot.py backend/tests/test_db_exclude_tables_directus_collections.py backend/tests/test_admin_gate_audit.py
git commit -m "test(C-1e): extend CI disallow list + Directus exposure check for upload_batches"
```

---

## Task C-2: Migrate `GET /api/signage/media` → Directus `signage_media`

**Files:**
- Modify: `directus/snapshots/<latest>.yaml`
- Modify: `frontend/src/signage/lib/signageApi.ts` (add `listMedia`)
- Create: `backend/tests/fixtures/contracts/signage_media_list.json`
- Modify: `backend/app/routers/signage_admin/media.py` (delete the list handler)
- Modify: `backend/tests/test_openapi_paths_snapshot.py`
- Modify: `backend/tests/test_db_exclude_tables_directus_collections.py`

- [ ] **Step 1: Register `signage_media` collection in Directus snapshot**

Permissions: Admin role gets `read` on all fields. Viewer role gets no permissions on `signage_media` (admin-only collection). The v1.22 LISTEN/NOTIFY trigger is already wired — no schema change.

- [ ] **Step 2: Apply snapshot + smoke-test permission**

```bash
docker compose exec directus npx directus schema apply --yes ./snapshots/<file>.yaml
# Admin can read:
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8055/items/signage_media | jq '.data | length'
# Viewer cannot:
curl -H "Authorization: Bearer $VIEWER_TOKEN" http://localhost:8055/items/signage_media -o - | jq '.errors[0].extensions.code'
# Expected: "FORBIDDEN" or equivalent
```

- [ ] **Step 3: Add `listMedia` to the FE adapter**

In `frontend/src/signage/lib/signageApi.ts`:

```ts
import { readItems } from "@directus/sdk";
import { directus } from "../../lib/directus";

export async function listMedia(): Promise<SignageMedia[]> {
  return await directus.request(readItems("signage_media", { sort: ["-created_at"] }));
}
```

Update existing call sites in `frontend/src/signage/` that previously used `fetch('/api/signage/media')`.

- [ ] **Step 4: Add the contract-snapshot fixture**

Create `backend/tests/fixtures/contracts/signage_media_list.json` matching the v1.22 contract pattern.

- [ ] **Step 5: Delete the FastAPI list handler**

In `backend/app/routers/signage_admin/media.py`, remove the `@router.get("")` (or whatever path lists media). Keep `PATCH`, `DELETE`, `POST /pptx`, `POST /{id}/reconvert` — those are compute-justified.

- [ ] **Step 6: Extend CI disallow + Directus-exposure tests**

Add `"/api/signage/media"` (GET) to OpenAPI disallow list. Add `signage_media` to the Directus-exposed-tables set (only if not already there from an earlier round).

- [ ] **Step 7: Run full check**

Run: `docker compose exec api pytest -q && ./scripts/smoke-rebuild.sh && (cd frontend && npm run build)`
Expected: all green.

- [ ] **Step 8: Commit (5-commit split)**

```bash
git add directus/snapshots/
git commit -m "feat(C-2a): expose signage_media via Directus collection (admin-only)"

git add frontend/src/signage/lib/signageApi.ts frontend/src/signage/
git commit -m "feat(C-2b): listMedia() via Directus SDK"

git add backend/tests/fixtures/contracts/signage_media_list.json
git commit -m "test(C-2c): contract fixture for signage_media list"

git add backend/app/routers/signage_admin/media.py
git commit -m "refactor(C-2d): delete GET /api/signage/media FastAPI route"

git add backend/tests/test_openapi_paths_snapshot.py backend/tests/test_db_exclude_tables_directus_collections.py
git commit -m "test(C-2e): CI disallow + Directus exposure for signage_media list"
```

---

## Task C-3: Migrate `GET /api/signage/media/{id}` → Directus `signage_media`

**Files:**
- Modify: `frontend/src/signage/lib/signageApi.ts` (add `getMedia`)
- Create: `backend/tests/fixtures/contracts/signage_media_item.json`
- Modify: `backend/app/routers/signage_admin/media.py` (delete the get-by-id handler)
- Modify: `backend/tests/test_openapi_paths_snapshot.py`

(Directus permissions already set in C-2; no snapshot change needed.)

- [ ] **Step 1: Add `getMedia` to the FE adapter**

```ts
import { readItem } from "@directus/sdk";

export async function getMedia(id: string): Promise<SignageMedia> {
  return await directus.request(readItem("signage_media", id));
}
```

- [ ] **Step 2: Add contract fixture**

Create `backend/tests/fixtures/contracts/signage_media_item.json` with one full Directus item response.

- [ ] **Step 3: Delete the FastAPI handler**

Remove `@router.get("/{media_id}")` from `signage_admin/media.py`.

- [ ] **Step 4: Extend OpenAPI disallow list**

Add `"/api/signage/media/{media_id}"` (GET) to the disallow set.

- [ ] **Step 5: Run full check**

Run: `docker compose exec api pytest -q && ./scripts/smoke-rebuild.sh && (cd frontend && npm run build)`
Expected: PASS.

- [ ] **Step 6: Commit (4-commit split — no Directus snapshot change)**

```bash
git add frontend/src/signage/lib/signageApi.ts frontend/src/signage/
git commit -m "feat(C-3a): getMedia(id) via Directus SDK"

git add backend/tests/fixtures/contracts/signage_media_item.json
git commit -m "test(C-3b): contract fixture for signage_media item"

git add backend/app/routers/signage_admin/media.py
git commit -m "refactor(C-3c): delete GET /api/signage/media/{id} FastAPI route"

git add backend/tests/test_openapi_paths_snapshot.py
git commit -m "test(C-3d): CI disallow GET /api/signage/media/{id}"
```

---

## Task C-4: Migrate `POST /api/signage/media` (non-PPTX kinds) → Directus

**Files:**
- Modify: `directus/snapshots/<latest>.yaml` (grant Admin `create` on `signage_media`)
- Modify: `frontend/src/signage/lib/signageApi.ts` (add `createMedia` with the PPTX branch)
- Create: `backend/tests/fixtures/contracts/signage_media_create.json`
- Modify: `backend/app/routers/signage_admin/media.py` (the POST stays for `kind=='pptx'` only — see existing `POST /pptx` route which is the compute path)
- Modify: `backend/tests/test_openapi_paths_snapshot.py`

- [ ] **Step 1: Confirm the FastAPI shape**

The non-PPTX `POST /api/signage/media` is the create-by-URL or create-by-image path. The PPTX path lives at `POST /api/signage/media/pptx` (separate route, BackgroundTasks-justified — stays). Verify by inspecting `signage_admin/media.py`:

Run: `grep -n "@router.post" backend/app/routers/signage_admin/media.py`

If the non-PPTX POST shares the path `/api/signage/media` with no kind branching server-side, deletion is straightforward. If it branches on `kind`, the deletion removes the non-PPTX branch only and rejects PPTX uploads from that path; PPTX continues to use `POST /api/signage/media/pptx`.

- [ ] **Step 2: Update Directus permissions**

In the snapshot, grant Admin `create` on `signage_media`. Apply.

- [ ] **Step 3: Implement `createMedia` in the FE adapter with the kind branch**

```ts
import { createItem } from "@directus/sdk";

/**
 * Create a media row.
 *
 * BRANCHING: PPTX kind requires server-side conversion (BackgroundTasks)
 * and stays on FastAPI's POST /api/signage/media/pptx. All other kinds
 * (image, url) go through Directus (compute-justified rubric clause 1
 * does not apply — pure CRUD).
 */
export async function createMedia(input: CreateMediaInput): Promise<SignageMedia> {
  if (input.kind === "pptx") {
    // existing FastAPI multipart upload path — unchanged
    return await uploadPptxMedia(input);
  }
  return await directus.request(createItem("signage_media", input));
}
```

Document the branch in the module docstring at the top of `signageApi.ts`.

- [ ] **Step 4: Add contract fixture**

Create `backend/tests/fixtures/contracts/signage_media_create.json` with a Directus create response payload (non-PPTX).

- [ ] **Step 5: Delete the non-PPTX FastAPI POST handler**

Remove the relevant `@router.post(...)` (the one that handles non-PPTX kinds at `/api/signage/media`). The `/pptx` and `/{id}/reconvert` POSTs stay.

- [ ] **Step 6: Add the deleted route to OpenAPI disallow list**

Add `("/api/signage/media", "POST")` (or whatever the canonical disallow-list shape is in this repo) to the disallow set.

- [ ] **Step 7: Run full check**

Run: `docker compose exec api pytest -q && ./scripts/smoke-rebuild.sh && (cd frontend && npm run build)`
Expected: PASS.

- [ ] **Step 8: Commit (5-commit split)**

```bash
git add directus/snapshots/
git commit -m "feat(C-4a): grant Admin create on signage_media in Directus"

git add frontend/src/signage/lib/signageApi.ts
git commit -m "feat(C-4b): createMedia branches on kind=pptx"

git add backend/tests/fixtures/contracts/signage_media_create.json
git commit -m "test(C-4c): contract fixture for signage_media create"

git add backend/app/routers/signage_admin/media.py
git commit -m "refactor(C-4d): delete non-PPTX POST /api/signage/media (stays in Directus)"

git add backend/tests/test_openapi_paths_snapshot.py
git commit -m "test(C-4e): CI disallow non-PPTX POST /api/signage/media"
```

---

## Task C-5: Phase C verification — end-to-end

- [ ] **Step 1: Smoke-rebuild**

Run: `./scripts/smoke-rebuild.sh`
Expected: exit 0.

- [ ] **Step 2: Manual Directus permission smoke**

```bash
# Viewer can list upload_batches
curl -H "Authorization: Bearer $VIEWER_TOKEN" http://localhost:8055/items/upload_batches | jq '.data | type'  # array

# Viewer CANNOT list signage_media
curl -s -H "Authorization: Bearer $VIEWER_TOKEN" http://localhost:8055/items/signage_media | jq '.errors[0].extensions.code'  # FORBIDDEN

# Admin can create signage_media (non-PPTX)
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"kind":"image","url":"https://example.com/x.jpg","name":"smoke"}' \
  http://localhost:8055/items/signage_media | jq '.data.id'  # uuid
```

- [ ] **Step 3: Frontend build**

Run: `cd frontend && npm run build`
Expected: exit 0, zero `error TS`.

If any check fails, fix before Phase D.

---

# PHASE D — ADR-0001 amendment + compute-justified rubric

## Task D-1: Append the rubric to ADR-0001

**Files:**
- Modify: `docs/adr/0001-directus-fastapi-split.md`

- [ ] **Step 1: Append the rubric block**

At the end of the ADR, add:

```markdown
## Compute-Justified Rubric (added v1.23)

A FastAPI write endpoint may read or mutate a table that Directus also exposes only if it satisfies at least one of:

1. **Side effect outside Postgres** — file I/O, SSE fanout, external API call, scheduler reschedule, BackgroundTask.
2. **Cryptographic operation** — Fernet encrypt/decrypt of a column Directus must not see in plaintext.
3. **Multi-row atomic compute** — e.g. bulk DELETE+INSERT in one transaction.
4. **Custom error contract the FE depends on** — e.g. structured `409 {detail, schedule_ids}`.

Endpoints meeting none of these MUST move to Directus. New compute endpoints declare which clause justifies them in the module docstring with a `Compute-justified:` tag. Enforced by `backend/tests/test_compute_justified_rubric.py`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/adr/0001-directus-fastapi-split.md
git commit -m "docs(D-01): ADR-0001 compute-justified rubric"
```

---

## Task D-2: Add `Compute-justified:` tags to surviving compute modules

**Files:** all of:
- `backend/app/routers/signage_admin/playlists.py`
- `backend/app/routers/signage_admin/playlist_items.py`
- `backend/app/routers/signage_admin/media.py`
- `backend/app/routers/signage_admin/devices.py`
- `backend/app/routers/signage_admin/analytics.py`
- `backend/app/routers/signage_admin/resolved.py`
- `backend/app/routers/sensors.py`
- `backend/app/routers/settings.py`
- `backend/app/routers/uploads.py`
- `backend/app/routers/sync.py`
- `backend/app/routers/kpis.py`
- `backend/app/routers/hr_kpis.py`
- `backend/app/routers/hr_overtime.py`
- `backend/app/routers/signage_pair.py`
- `backend/app/routers/signage_player.py`

For each file, add a one-line `Compute-justified:` tag in its module docstring.

- [ ] **Step 1: signage_admin group**

| File | Tag |
|---|---|
| `playlists.py` | `Compute-justified: clause 1 (SSE fanout) + clause 4 (structured 409 schedule_ids).` |
| `playlist_items.py` | `Compute-justified: clause 1 (SSE fanout).` |
| `media.py` | `Compute-justified: clause 1 (SSE fanout) + clause 4 (structured 409 playlist_ids) + clause 1 (BackgroundTasks for PPTX).` |
| `devices.py` | `Compute-justified: clause 1 (SSE fanout).` |
| `analytics.py` | `Compute-justified: clause 3 (multi-row aggregation compute).` |
| `resolved.py` | `Compute-justified: clause 1 (real-time resolver compute, not a stored shape).` |

Insert each tag at the end of the existing module docstring.

- [ ] **Step 2: Commit signage_admin group**

```bash
git add backend/app/routers/signage_admin/
git commit -m "docs(D-02a): Compute-justified tags on signage_admin/*"
```

- [ ] **Step 3: KPIs / HR group**

| File | Tag |
|---|---|
| `kpis.py` | `Compute-justified: clause 3 (multi-row KPI aggregation across periods).` |
| `hr_kpis.py` | `Compute-justified: clause 3 (multi-row HR KPI aggregation).` |
| `hr_overtime.py` | `Compute-justified: clause 3 (overtime compute across overlapping intervals).` |

```bash
git add backend/app/routers/kpis.py backend/app/routers/hr_kpis.py backend/app/routers/hr_overtime.py
git commit -m "docs(D-02b): Compute-justified tags on KPI/HR routers"
```

- [ ] **Step 4: Device-auth group**

| File | Tag |
|---|---|
| `signage_pair.py` | `Compute-justified: clause 2 (pairing-token Fernet encrypt).` |
| `signage_player.py` | `Compute-justified: clause 1 (SSE stream + resolver compute).` |

```bash
git add backend/app/routers/signage_pair.py backend/app/routers/signage_player.py
git commit -m "docs(D-02c): Compute-justified tags on device-auth routers"
```

- [ ] **Step 5: Settings/uploads/sensors/sync group**

| File | Tag |
|---|---|
| `settings.py` | `Compute-justified: clause 1 (APScheduler reschedule + logo MIME sniff/SVG sanitize).` |
| `uploads.py` | `Compute-justified: clause 1 (file parsing) + clause 3 (cascade delete).` |
| `sensors.py` | `Compute-justified: clause 2 (Fernet community write-side) + clause 1 (SNMP polling).` |
| `sync.py` | `Compute-justified: clause 1 (external Personio API call).` |

```bash
git add backend/app/routers/settings.py backend/app/routers/uploads.py backend/app/routers/sensors.py backend/app/routers/sync.py
git commit -m "docs(D-02d): Compute-justified tags on settings/uploads/sensors/sync"
```

---

## Task D-3: Add the CI guard `test_compute_justified_rubric.py`

**Files:**
- Create: `backend/tests/test_compute_justified_rubric.py`

- [ ] **Step 1: Write the failing test (so we see allowlist coverage)**

```python
"""CI guard: every /api/* compute route module declares a Compute-justified clause.

Phase D of docs/superpowers/specs/2026-04-28-backend-router-compute-crud-cleanup-design.md.

Walks ``app.routes``. For each /api/* route, finds the source module via
``route.endpoint.__module__`` and asserts the module's docstring contains
``Compute-justified:``. Viewer-only GETs that legitimately read shared tables
are listed in COMPUTE_RUBRIC_ALLOWLIST below.
"""
from __future__ import annotations

import importlib
import sys

from fastapi.routing import APIRoute

from app.main import app


# (path, frozenset(methods)) — viewer/public endpoints that read shared tables
# without compute. Keep small; additions reviewed.
COMPUTE_RUBRIC_ALLOWLIST: set[tuple[str, frozenset[str]]] = {
    ("/api/settings", frozenset({"GET"})),
    ("/api/settings/logo", frozenset({"GET"})),
}


def test_every_compute_route_module_declares_clause():
    api_routes = [
        r for r in app.routes
        if isinstance(r, APIRoute) and r.path.startswith("/api/")
    ]
    assert api_routes, "no /api/* routes registered"

    violations: list[str] = []
    for route in api_routes:
        methods = frozenset(m for m in route.methods if m != "HEAD")
        if (route.path, methods) in COMPUTE_RUBRIC_ALLOWLIST:
            continue
        if any((route.path, frozenset({m})) in COMPUTE_RUBRIC_ALLOWLIST for m in methods):
            continue

        mod_name = route.endpoint.__module__
        mod = sys.modules.get(mod_name) or importlib.import_module(mod_name)
        doc = (mod.__doc__ or "")
        if "Compute-justified:" not in doc:
            violations.append(
                f"{sorted(methods)} {route.path} (module {mod_name}) "
                f"is missing 'Compute-justified:' tag in its module docstring"
            )

    assert not violations, "\n  - " + "\n  - ".join(violations)
```

- [ ] **Step 2: Run it**

Run: `docker compose exec api pytest backend/tests/test_compute_justified_rubric.py -v`
Expected: PASS (Task D-2 already added every required tag).

If it fails, the failure message lists exactly which module is missing a tag — go back and fix that module's docstring. Iterate until green.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_compute_justified_rubric.py
git commit -m "feat(D-03): test_compute_justified_rubric CI guard"
```

---

## Task D-4: Add "How to choose: Directus vs FastAPI?" to architecture.md

**Files:**
- Modify: `docs/architecture.md`

- [ ] **Step 1: Append the section**

```markdown
## How to choose: Directus vs FastAPI?

Default: Directus. A new endpoint that reads or writes a Postgres table goes through Directus unless it meets the **Compute-Justified Rubric** in [ADR-0001](./adr/0001-directus-fastapi-split.md):

1. Side effect outside Postgres (file I/O, SSE fanout, external API call, scheduler reschedule, BackgroundTask)
2. Cryptographic operation (Fernet on a column Directus must not see in plaintext)
3. Multi-row atomic compute (e.g. bulk DELETE+INSERT in one transaction)
4. Custom error contract the FE depends on

If a new compute endpoint lands in FastAPI, declare the clause in the module docstring (`Compute-justified: clause N (reason).`). The CI guard `backend/tests/test_compute_justified_rubric.py` enforces this.
```

- [ ] **Step 2: Commit**

```bash
git add docs/architecture.md
git commit -m "docs(D-04): architecture.md — Directus vs FastAPI section"
```

---

## Task D-5: End-state verification

- [ ] **Step 1: Full backend tests**

Run: `docker compose exec api pytest -q`
Expected: green, including `test_admin_gate_audit.py` and `test_compute_justified_rubric.py`.

- [ ] **Step 2: Smoke-rebuild**

Run: `./scripts/smoke-rebuild.sh`
Expected: exit 0.

- [ ] **Step 3: Frontend build**

Run: `cd frontend && npm run build`
Expected: exit 0, zero `error TS`.

- [ ] **Step 4: OpenAPI snapshot zero-overlap**

Run: `docker compose exec api pytest backend/tests/test_openapi_paths_snapshot.py -v`
Expected: PASS — confirms zero of `/api/uploads` (GET), `/api/signage/media` (GET, POST non-PPTX), `/api/signage/media/{id}` (GET) appear in the live OpenAPI.

- [ ] **Step 5: ADR sanity check**

Run: `grep -n "Compute-Justified Rubric" docs/adr/0001-directus-fastapi-split.md`
Expected: one match.

- [ ] **Step 6: Final summary commit (optional)**

If you want a single tagged commit marking the end of v1.23 cleanup:

```bash
git commit --allow-empty -m "chore: v1.23 router compute/CRUD boundary cleanup complete"
```

---

# Self-review notes

- All four spec phases (A, B, C, D) have explicit task coverage.
- All four spec migrations in Phase C are individually planned (C-1..C-4).
- All four duplicate helpers in Phase A are individually swapped (A-2..A-5).
- All five files in spec § Phase B "File alignment" are addressed (B-2..B-4).
- Both CI guards (`test_admin_gate_audit.py` from B-1 and `test_compute_justified_rubric.py` from D-3) are concretely implemented.
- ADR-0001 amendment text is verbatim per spec (D-1).
- All compute-module tags are concrete strings (D-2), not placeholders.
- The `affected=` + `deleted=True` invariant from spec § Phase A "Invariants to preserve" is exercised in test A-1 and used in A-2's DELETE path.
- Frontend `createMedia` PPTX branch documented per spec § Phase C "Risks and mitigations" (C-4).
- Sequential dependency respected: A and B are pure refactors, C is wire-affecting, D ratifies. Each phase ends with green verification before the next begins (B-6, C-5, D-5).

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-28-backend-router-compute-crud-cleanup.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
