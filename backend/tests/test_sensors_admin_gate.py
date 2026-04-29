"""Router dep-audit + 401/403/200 contract tests for /api/sensors/* (SEN-BE-13).

Uses the project's existing async test harness (httpx.AsyncClient + ASGITransport +
LifespanManager via the `client` fixture in conftest.py). That pattern is
battle-tested against pytest-asyncio loop handling in this repo — switching to
starlette.TestClient here would reintroduce the "event loop is closed" fragility
that conftest.py's `client` fixture already solves.
"""
from pathlib import Path

from fastapi.routing import APIRoute

from app.main import app
from app.security.directus_auth import require_admin
from tests.test_directus_auth import _mint, ADMIN_UUID, VIEWER_UUID


def _walk_deps(deps):
    out = []
    for d in deps:
        out.append(d.call)
        out.extend(_walk_deps(d.dependencies))
    return out


def test_sensor_routes_registered():
    sensor_routes = [
        r for r in app.routes
        if isinstance(r, APIRoute) and r.path.startswith("/api/sensors")
    ]
    # list, create, update, delete, readings, poll-now, snmp-probe, snmp-walk, status
    assert len(sensor_routes) >= 8, (
        f"expected >=8 /api/sensors/* routes, got {len(sensor_routes)}: "
        f"{[(r.path, sorted(r.methods)) for r in sensor_routes]}"
    )


def test_every_sensor_route_has_require_admin():
    """SEN-BE-13 / PITFALLS M-1: every /api/sensors/* route has require_admin in its dep chain."""
    sensor_routes = [
        r for r in app.routes
        if isinstance(r, APIRoute) and r.path.startswith("/api/sensors")
    ]
    assert sensor_routes, "no /api/sensors/* routes — router include missing?"
    for route in sensor_routes:
        all_calls = _walk_deps(route.dependant.dependencies)
        assert require_admin in all_calls, (
            f"route {sorted(route.methods)} {route.path} missing require_admin in dep chain"
        )


async def test_no_token_returns_401(client):
    r = await client.get("/api/sensors")
    assert r.status_code == 401


async def test_viewer_token_returns_403_admin_body(client):
    token = _mint(VIEWER_UUID)
    r = await client.get("/api/sensors", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    assert r.json() == {"detail": "admin role required"}


async def test_admin_token_returns_200_for_list(client):
    token = _mint(ADMIN_UUID)
    r = await client.get("/api/sensors", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    # PITFALLS C-3: SensorRead must NEVER echo community
    for row in data:
        assert "community" not in row, (
            f"community leaked in GET /api/sensors response: {row}"
        )


def test_poll_now_wraps_in_wait_for():
    """SEN-BE-10: poll_now uses asyncio.wait_for(..., timeout=30)."""
    text = (Path(__file__).resolve().parents[1] / "app" / "routers" / "sensors.py").read_text()
    assert "asyncio.wait_for" in text, "poll-now handler must use asyncio.wait_for"
    assert "timeout=30" in text, "poll-now handler must wrap poll_all in timeout=30"
