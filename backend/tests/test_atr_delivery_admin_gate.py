from fastapi.routing import APIRoute

from app.main import app
from app.security.directus_auth import require_admin, require_atr_fair
from tests._auth import QS_UUID, VIEWER_UUID, mint


def _walk(deps):
    out = []
    for d in deps:
        out.append(d.call); out.extend(_walk(d.dependencies))
    return out


def test_delivery_routes_gated():
    routes = [r for r in app.routes
              if isinstance(r, APIRoute) and r.path.startswith("/api/atr/deliveries")]
    assert len(routes) >= 7
    for r in routes:
        calls = _walk(r.dependant.dependencies)
        assert require_admin in calls or require_atr_fair in calls, r.path


async def test_viewer_403(client):
    r = await client.get("/api/atr/deliveries",
                         headers={"Authorization": f"Bearer {mint(VIEWER_UUID)}"})
    assert r.status_code == 403


async def test_qs_allowed(client):
    r = await client.get("/api/atr/deliveries",
                         headers={"Authorization": f"Bearer {mint(QS_UUID)}"})
    assert r.status_code not in (401, 403)
