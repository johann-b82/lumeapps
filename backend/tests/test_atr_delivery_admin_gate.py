from fastapi.routing import APIRoute

from app.main import app
from app.security.directus_auth import require_admin
from tests._auth import VIEWER_UUID, mint


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
        assert require_admin in _walk(r.dependant.dependencies), r.path


async def test_viewer_403(client):
    r = await client.get("/api/atr/deliveries",
                         headers={"Authorization": f"Bearer {mint(VIEWER_UUID)}"})
    assert r.status_code == 403
