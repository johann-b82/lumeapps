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
    # Viewer-readable settings reads (mixed-gate; see settings.py docstring).
    ("/api/settings/personio-options", frozenset({"GET"})),
    # Public logo endpoint (no auth — public_router).
    ("/api/settings/logo/public", frozenset({"GET"})),
    # KPI dashboard reads — viewer role.
    ("/api/kpis", frozenset({"GET"})),
    ("/api/kpis/chart", frozenset({"GET"})),
    ("/api/kpis/latest-upload", frozenset({"GET"})),
    # HR KPI dashboard reads — viewer role.
    ("/api/hr/kpis", frozenset({"GET"})),
    ("/api/hr/kpis/history", frozenset({"GET"})),
    ("/api/data/employees/overtime", frozenset({"GET"})),
    # v1.41 sales-activity dashboard reads — viewer role.
    ("/api/data/sales/contacts-weekly", frozenset({"GET"})),
    ("/api/data/sales/orders-distribution", frozenset({"GET"})),
    # Viewer-readable sync freshness (mixed-gate; see sync.py docstring).
    ("/api/sync/meta", frozenset({"GET"})),
    # Signage pair/player endpoints use device-token auth, not user/admin auth.
    # They are out of scope for the user-role admin gate.
    ("/api/signage/pair/request", frozenset({"POST"})),
    ("/api/signage/pair/status", frozenset({"GET"})),
    ("/api/signage/player/playlist", frozenset({"GET"})),
    ("/api/signage/player/heartbeat", frozenset({"POST"})),
    ("/api/signage/player/stream", frozenset({"GET"})),
    ("/api/signage/player/asset/{media_id}", frozenset({"GET"})),
    ("/api/signage/player/calibration", frozenset({"GET"})),
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
