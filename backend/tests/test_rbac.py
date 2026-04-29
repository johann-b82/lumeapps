"""
Phase 28 RBAC matrix — exhaustive per-route × per-role test.

Source of truth for route classification: .planning/phases/28-*/28-RESEARCH.md
Covers: RBAC-01, RBAC-02, RBAC-04, RBAC-05 (the file itself is the machine-readable contract).
"""
import pytest
from httpx import AsyncClient, ASGITransport

from tests.test_directus_auth import _mint, ADMIN_UUID, VIEWER_UUID
from app.main import app

# (method, path)
# Both Viewer and Admin JWTs must return status != 401 and != 403
READ_ROUTES = [
    ("GET", "/api/kpis"),
    ("GET", "/api/kpis/chart"),
    ("GET", "/api/kpis/latest-upload"),
    ("GET", "/api/hr/kpis"),
    ("GET", "/api/hr/kpis/history"),
    ("GET", "/api/data/employees/overtime?date_from=2026-01-01&date_to=2026-01-31"),
    ("GET", "/api/settings"),
    ("GET", "/api/settings/personio-options"),
    ("GET", "/api/settings/logo"),
    ("GET", "/api/uploads"),
    ("GET", "/api/sync/meta"),
]
# Phase 70 (MIG-SIGN-04) D-09 — devices list/by-id migrated to Directus
# signage_devices collection. New per-device resolved playlist endpoint
# `GET /api/signage/resolved/{device_id}` is admin-gated (router-level
# require_admin in signage_admin/__init__.py per cross-cutting hazard #5
# — same RBAC class as the rest of signage_admin). PATCH
# /devices/{id}/calibration STAYS in FastAPI per D-00j and is exercised
# in tests/test_signage_calibration.py (own RBAC asserts). The migrated
# read paths (GET /api/signage/devices, GET /api/signage/devices/{id})
# were never in READ_ROUTES because signage routes have always been
# admin-gated, not read-class.

# Viewer JWT → 403 + {"detail": "admin role required"}
# Admin JWT  → not 403 (business-logic 4xx/5xx acceptable)
MUTATION_ROUTES = [
    ("POST",   "/api/upload"),
    ("DELETE", "/api/uploads/99999"),
    ("POST",   "/api/sync"),
    ("POST",   "/api/sync/test"),
    ("PUT",    "/api/settings"),
    ("POST",   "/api/settings/logo"),
    # Phase 70 D-09: admin-only signage_admin/resolved router.
    # Admin reaches the handler (404 expected — fake UUID — but not 403).
    # Viewer must get 403 with canonical {"detail": "admin role required"}.
    ("GET",    "/api/signage/resolved/00000000-0000-4000-a000-000000000001"),
]


@pytest.mark.parametrize("method,path", READ_ROUTES)
@pytest.mark.parametrize("role_uuid", [VIEWER_UUID, ADMIN_UUID])
async def test_read_routes_allow_both_roles(method, path, role_uuid):
    token = _mint(role_uuid)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.request(method, path, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code != 401, (
        f"{method} {path} returned 401 for role {role_uuid}; auth broke"
    )
    assert r.status_code != 403, (
        f"{method} {path} returned 403 for role {role_uuid}; "
        f"unexpected authz block — body={r.text}"
    )


@pytest.mark.parametrize("method,path", MUTATION_ROUTES)
async def test_mutation_routes_deny_viewer(method, path):
    token = _mint(VIEWER_UUID)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.request(method, path, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403, (
        f"{method} {path} expected 403 for viewer, got {r.status_code}: {r.text}"
    )
    assert r.json() == {"detail": "admin role required"}, (
        f"{method} {path} 403 body was {r.json()!r}, not the canonical shape"
    )


@pytest.mark.parametrize("method,path", MUTATION_ROUTES)
async def test_mutation_routes_allow_admin(method, path):
    token = _mint(ADMIN_UUID)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.request(method, path, headers={"Authorization": f"Bearer {token}"})
    # Auth + authz passed. Business validation may return 200/400/404/422/500.
    # The ONLY disallowed code is 403 (would mean require_admin incorrectly rejected Admin).
    assert r.status_code != 403, (
        f"{method} {path} returned 403 for admin, but admin must pass authz: {r.text}"
    )
    # 401 would also indicate test harness issue
    assert r.status_code != 401, (
        f"{method} {path} returned 401 for admin; JWT minting broke"
    )


# --- RBAC-04: stateless-JWT role propagation ---
# Same user_id, two tokens with different role UUIDs → different authorization outcomes.
# Demonstrates: promoting a Viewer to Admin in Directus UI (which mints new JWTs with
# the new role UUID) takes effect on the next request without any backend code path.
async def test_rbac_04_same_user_role_swap_via_jwt():
    user_id = "00000000-0000-0000-0000-00000000abcd"
    viewer_token = _mint(VIEWER_UUID, user_id=user_id)
    admin_token  = _mint(ADMIN_UUID,  user_id=user_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r_viewer = await c.put(
            "/api/settings",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        r_admin = await c.put(
            "/api/settings",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert r_viewer.status_code == 403
    assert r_viewer.json() == {"detail": "admin role required"}
    assert r_admin.status_code != 403, (
        f"Same user with Admin-role JWT still 403'd: {r_admin.text}"
    )
