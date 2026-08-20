"""QS role scope: FAIR + ATR only, nothing else.

The interim, hard-wired QS role (see Role.QS / require_atr_fair) may reach the
FAIR and ATR modules and must be blocked everywhere else — both the
viewer-readable dashboards (require_dashboard_read excludes QS) and the
admin-only modules (require_admin excludes QS). Regression asserts confirm
Viewer/Admin behaviour is unchanged.
"""
import pytest

from tests._auth import ADMIN_UUID, QS_UUID, VIEWER_UUID, mint


def _auth(role_uuid: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint(role_uuid)}"}


# --- QS is admitted to FAIR + ATR ---
QS_ALLOWED = [
    "/api/atr/parts",
    "/api/atr/deliveries",
    "/api/fair/projects",
]


@pytest.mark.parametrize("path", QS_ALLOWED)
async def test_qs_allowed_on_fair_and_atr(client, path):
    r = await client.get(path, headers=_auth(QS_UUID))
    assert r.status_code not in (401, 403), f"QS unexpectedly blocked on {path}: {r.text}"


# --- QS is blocked on the viewer dashboards (require_dashboard_read) ---
QS_BLOCKED_DASHBOARDS = [
    "/api/kpis",
    "/api/hr/kpis",
    "/api/hr/org-chart",
    "/api/finance/material-cost-ratio",
    "/api/quality/complaint-rate",
    "/api/settings",
    "/api/sync/meta",
]


@pytest.mark.parametrize("path", QS_BLOCKED_DASHBOARDS)
async def test_qs_blocked_on_dashboards(client, path):
    r = await client.get(path, headers=_auth(QS_UUID))
    assert r.status_code == 403, f"QS should be 403 on {path}, got {r.status_code}: {r.text}"


# --- QS is blocked on admin-only modules (require_admin) ---
QS_BLOCKED_ADMIN = [
    "/api/sensors",
]


@pytest.mark.parametrize("path", QS_BLOCKED_ADMIN)
async def test_qs_blocked_on_admin_modules(client, path):
    r = await client.get(path, headers=_auth(QS_UUID))
    assert r.status_code == 403, f"QS should be 403 on {path}, got {r.status_code}: {r.text}"


async def test_qs_blocked_on_uploads(client):
    """Uploads has no GET — its list read lives in Directus (see DISALLOWED_PATHS
    in test_openapi_paths_snapshot.py). Probe a method that actually exists, so
    this asserts the admin gate rather than a 404 for a missing route.
    """
    r = await client.delete(
        "/api/uploads/00000000-0000-0000-0000-000000000000", headers=_auth(QS_UUID)
    )
    assert r.status_code == 403, f"QS should be 403 on uploads delete, got {r.status_code}: {r.text}"


# --- Regression: Viewer/Admin behaviour unchanged ---
async def test_viewer_still_blocked_on_atr_fair(client):
    for path in QS_ALLOWED:
        r = await client.get(path, headers=_auth(VIEWER_UUID))
        assert r.status_code == 403, f"Viewer should be 403 on {path}, got {r.status_code}"


async def test_viewer_still_allowed_on_dashboards(client):
    r = await client.get("/api/kpis", headers=_auth(VIEWER_UUID))
    assert r.status_code != 403, "Viewer must still read the KPI dashboard"


async def test_admin_allowed_on_atr_fair_and_dashboards(client):
    for path in QS_ALLOWED + ["/api/kpis"]:
        r = await client.get(path, headers=_auth(ADMIN_UUID))
        assert r.status_code not in (401, 403), f"Admin unexpectedly blocked on {path}: {r.text}"
