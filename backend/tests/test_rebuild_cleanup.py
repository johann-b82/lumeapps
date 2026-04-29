"""Rebuild persistence harness — CLEANUP stage (Phase 7 Plan 06).

Called by `trap cleanup EXIT` in `scripts/smoke-rebuild.sh`. Restores the
app_settings singleton to canonical DEFAULT_SETTINGS so the developer's
local stack isn't left in "Rebuild Test Corp" state after the harness runs
(or fails partway through).

Overrides the autouse `reset_settings` fixture to a no-op — this module *is*
the reset; we drive it explicitly via PUT /api/settings so the logo blob is
also cleared (per D-07, PUT with the full payload nulls logo_data/mime).
"""
import pytest
import pytest_asyncio

from app.defaults import DEFAULT_SETTINGS


@pytest_asyncio.fixture(autouse=True)
async def reset_settings():
    yield


pytestmark = pytest.mark.asyncio


async def test_reset_to_defaults(client):
    payload = dict(DEFAULT_SETTINGS)
    r = await client.put("/api/settings", json=payload)
    assert r.status_code == 200, r.text
