"""SGN-BE-09 (Phase 43): router dep-audit.

Walks every route under /api/signage and asserts the correct router-level
gate is present in the dependant tree.

INTENTIONAL EXCEPTIONS: PUBLIC_SIGNAGE_ROUTES are the two public pair
endpoints (/request, /status) — documented in Phase 42 Plan 02 SUMMARY
(.planning/phases/42-device-auth-pairing-flow/42-02-signage-pair-router-SUMMARY.md).
Adding any new public signage route requires an explicit entry here — no
silent gate leaks.
"""
from fastapi.routing import APIRoute

from app.main import app
from app.security.device_auth import get_current_device
from app.security.directus_auth import require_admin

PUBLIC_SIGNAGE_ROUTES = {
    "/api/signage/pair/request",
    "/api/signage/pair/status",
}


def _walk_deps(deps):
    out = []
    for d in deps:
        out.append(d.call)
        out.extend(_walk_deps(d.dependencies))
    return out


def test_signage_admin_routes_have_require_admin():
    found = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/signage"):
            continue
        if route.path in PUBLIC_SIGNAGE_ROUTES:
            continue
        if route.path.startswith("/api/signage/player/"):
            continue
        found.append(route.path)
        all_calls = _walk_deps(route.dependant.dependencies)
        assert require_admin in all_calls, (
            f"admin route {route.path} (method={list(route.methods)}) "
            f"missing require_admin in dependant tree"
        )
    # Sanity: we actually walked some admin routes (not vacuously true)
    assert len(found) > 0, "no /api/signage admin routes found — wiring broken?"


def test_signage_player_routes_have_get_current_device():
    found = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/signage/player/"):
            continue
        found.append(route.path)
        all_calls = _walk_deps(route.dependant.dependencies)
        assert get_current_device in all_calls, (
            f"player route {route.path} (method={list(route.methods)}) "
            f"missing get_current_device in dependant tree"
        )
    assert len(found) >= 2, (
        f"expected >=2 player routes (/playlist, /heartbeat), found {found}"
    )


def test_public_signage_routes_are_explicitly_allowed():
    """Guard against adding a public signage route without updating the allow-list."""
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/signage"):
            continue
        if route.path.startswith("/api/signage/player/"):
            continue
        if route.path in PUBLIC_SIGNAGE_ROUTES:
            continue
        all_calls = _walk_deps(route.dependant.dependencies)
        # All remaining signage routes MUST have require_admin (covered by test above);
        # this test exists so changes to PUBLIC_SIGNAGE_ROUTES surface in review.
        assert require_admin in all_calls
