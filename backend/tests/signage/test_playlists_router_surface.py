"""Phase 69 MIG-SIGN-03 regression: playlists.py surface after route removal.

After Plan 69-01, only ``DELETE /{playlist_id}`` survives in
``backend/app/routers/signage_admin/playlists.py``. POST/GET/PATCH/PUT-tags
have moved to Directus collections. v1.23 Phase A-2 deduplicated the
local ``_notify_playlist_changed`` helper — the DELETE handler now uses
``signage_broadcast.notify_playlist_changed`` directly.
"""
from __future__ import annotations

from app.routers.signage_admin import playlists
from app.services import signage_broadcast


def test_only_delete_route_remains() -> None:
    """No POST/GET/PATCH/PUT routes should remain on the playlists router."""
    methods_seen: set[str] = set()
    for route in playlists.router.routes:
        # APIRoute objects expose ``methods``; mounts/etc. won't.
        methods = getattr(route, "methods", None) or set()
        methods_seen.update(methods)

    # HEAD is auto-added alongside GET by Starlette; if any GET-shaped route
    # remained, HEAD would appear. Asserting both are absent catches that.
    forbidden = {"POST", "GET", "PATCH", "PUT", "HEAD"}
    leaked = forbidden & methods_seen
    assert not leaked, f"unexpected migrated routes still exposed: {leaked}"


def test_delete_route_present() -> None:
    """The 409-bearing DELETE handler is the sole surviving endpoint."""
    delete_routes = [
        r
        for r in playlists.router.routes
        if "DELETE" in (getattr(r, "methods", None) or set())
        and getattr(r, "path", "").endswith("/{playlist_id}")
    ]
    assert len(delete_routes) == 1, (
        f"expected exactly 1 DELETE /{{playlist_id}} route, found {len(delete_routes)}"
    )


def test_notify_helper_retained() -> None:
    """The shared notify helper from signage_broadcast must remain callable —
    the surviving DELETE handler still depends on it (v1.23 Phase A-2)."""
    assert hasattr(signage_broadcast, "notify_playlist_changed")
    assert callable(signage_broadcast.notify_playlist_changed)
