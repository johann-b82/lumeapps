"""Every /api/email/* route must carry require_admin (mirrors test_atr_admin_gate)."""
from fastapi.routing import APIRoute

from app.main import app
from app.security.directus_auth import require_admin
from tests._auth import VIEWER_UUID, mint


def _walk_deps(deps):
    out = []
    for d in deps:
        out.append(d.call)
        out.extend(_walk_deps(d.dependencies))
    return out


def test_email_routes_registered():
    routes = [r for r in app.routes
              if isinstance(r, APIRoute) and r.path.startswith("/api/email")]
    # /api/email/test and /api/email/send
    assert len(routes) >= 2, [(r.path, sorted(r.methods)) for r in routes]


def test_every_email_route_has_require_admin():
    routes = [r for r in app.routes
              if isinstance(r, APIRoute) and r.path.startswith("/api/email")]
    for route in routes:
        calls = _walk_deps(route.dependant.dependencies)
        assert require_admin in calls, f"{sorted(route.methods)} {route.path} missing require_admin"


async def test_viewer_gets_403(client):
    r = await client.post(
        "/api/email/test",
        json={"to": "x@firma.de"},
        headers={"Authorization": f"Bearer {mint(VIEWER_UUID)}"},
    )
    assert r.status_code == 403


async def test_no_token_gets_401(client):
    r = await client.post("/api/email/test", json={"to": "x@firma.de"})
    assert r.status_code == 401
