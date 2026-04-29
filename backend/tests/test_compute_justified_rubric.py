"""CI guard: every /api/* compute route module declares a Compute-justified clause.

Phase D of docs/superpowers/specs/2026-04-28-backend-router-compute-crud-cleanup-design.md.

Walks ``app.routes``. For each /api/* route, finds the source module via
``route.endpoint.__module__`` and asserts the module's docstring contains
``Compute-justified:``. Viewer-only GETs that legitimately read shared tables
are listed in COMPUTE_RUBRIC_ALLOWLIST below.
"""
from __future__ import annotations

import importlib
import sys

from fastapi.routing import APIRoute

from app.main import app


# (path, frozenset(methods)) — viewer/public endpoints that read shared tables
# without compute. Keep small; additions reviewed.
COMPUTE_RUBRIC_ALLOWLIST: set[tuple[str, frozenset[str]]] = {
    ("/api/settings", frozenset({"GET"})),
    ("/api/settings/logo", frozenset({"GET"})),
}


def test_every_compute_route_module_declares_clause():
    api_routes = [
        r for r in app.routes
        if isinstance(r, APIRoute) and r.path.startswith("/api/")
    ]
    assert api_routes, "no /api/* routes registered"

    violations: list[str] = []
    for route in api_routes:
        methods = frozenset(m for m in route.methods if m != "HEAD")
        if (route.path, methods) in COMPUTE_RUBRIC_ALLOWLIST:
            continue
        if any((route.path, frozenset({m})) in COMPUTE_RUBRIC_ALLOWLIST for m in methods):
            continue

        mod_name = route.endpoint.__module__
        mod = sys.modules.get(mod_name) or importlib.import_module(mod_name)
        doc = (mod.__doc__ or "")
        if "Compute-justified:" not in doc:
            violations.append(
                f"{sorted(methods)} {route.path} (module {mod_name}) "
                f"is missing 'Compute-justified:' tag in its module docstring"
            )

    assert not violations, "\n  - " + "\n  - ".join(violations)
