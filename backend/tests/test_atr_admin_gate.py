"""Every /api/atr/* route must be role-gated (mirrors test_sensors_admin_gate).

The catalog/delivery routers carry require_atr_fair (Admin + interim QS role);
the ATR *config* fileserver router stays require_admin. Both gates block Viewer.
"""
from fastapi.routing import APIRoute

from app.main import app
from app.security.directus_auth import require_admin, require_atr_fair
from tests._auth import QS_UUID, VIEWER_UUID, mint


def _walk_deps(deps):
    out = []
    for d in deps:
        out.append(d.call)
        out.extend(_walk_deps(d.dependencies))
    return out


def test_atr_routes_registered():
    routes = [r for r in app.routes
              if isinstance(r, APIRoute) and r.path.startswith("/api/atr")]
    # parts: list, get, create, patch, delete; import: preview, commit; template: get, patch, structure
    assert len(routes) >= 10, [(r.path, sorted(r.methods)) for r in routes]


def test_every_atr_route_is_role_gated():
    routes = [r for r in app.routes
              if isinstance(r, APIRoute) and r.path.startswith("/api/atr")]
    for route in routes:
        calls = _walk_deps(route.dependant.dependencies)
        assert require_admin in calls or require_atr_fair in calls, \
            f"{sorted(route.methods)} {route.path} missing role gate"


async def test_viewer_gets_403(client):
    r = await client.get("/api/atr/parts",
                         headers={"Authorization": f"Bearer {mint(VIEWER_UUID)}"})
    assert r.status_code == 403


async def test_qs_allowed(client):
    # The interim QS role reaches the ATR catalog (not 401/403).
    r = await client.get("/api/atr/parts",
                         headers={"Authorization": f"Bearer {mint(QS_UUID)}"})
    assert r.status_code not in (401, 403)


async def test_no_token_gets_401(client):
    r = await client.get("/api/atr/parts")
    assert r.status_code == 401
