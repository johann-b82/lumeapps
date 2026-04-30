"""Rebuild persistence harness — ASSERT stage (Phase 7 Plan 06, D-21/D-23).

Runs after `docker compose down && up --build`. Re-fetches the singleton and
verifies all seeded fields (8 settings + logo bytes) survived byte-exact.

CRITICAL (RESEARCH Pitfall 5): the conftest `reset_settings` autouse fixture
would wipe the persisted state we're verifying. This module overrides it to
a no-op so the post-rebuild state is preserved across test setup.

Skipped by default (would fail without prior seed state). The smoke-rebuild
script sets `LUMEAPPS_SMOKE_REBUILD_ASSERT=1` after the seed step to opt in.
"""
import os

import pytest_asyncio

from tests.test_rebuild_seed import REBUILD_SEED_PAYLOAD, RED_1X1_PNG

import pytest


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.environ.get("LUMEAPPS_SMOKE_REBUILD_ASSERT") != "1",
        reason="rebuild-assert stage; set LUMEAPPS_SMOKE_REBUILD_ASSERT=1 (smoke-rebuild.sh does this)",
    ),
]


# Module-level override: no-op out the conftest autouse reset.
@pytest_asyncio.fixture(autouse=True)
async def reset_settings():
    yield


async def test_all_fields_survive_rebuild(admin_client):
    r = await admin_client.get("/api/settings")
    assert r.status_code == 200, r.text
    body = r.json()
    for k, v in REBUILD_SEED_PAYLOAD.items():
        assert body[k] == v, f"{k} corrupted: expected {v!r}, got {body[k]!r}"
    assert body.get("logo_url") is not None, "logo_url went null after rebuild"


async def test_logo_bytes_survive_rebuild(admin_client):
    r = await admin_client.get("/api/settings/logo")
    assert r.status_code == 200, r.text
    assert r.content == RED_1X1_PNG, (
        f"logo bytes corrupted or replaced: got {len(r.content)} bytes"
    )
    assert r.headers["content-type"] == "image/png"
