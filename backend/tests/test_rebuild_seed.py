"""Rebuild persistence harness — SEED stage (Phase 7 Plan 06, D-21/D-23).

Seeds the app_settings singleton with a known payload and uploads a
deterministic 1x1 red PNG as the logo. The assert stage
(`test_rebuild_assert.py`) re-reads the state after a full
`docker compose down && up --build` and verifies byte-exact equality.

This file is invoked by `scripts/smoke-rebuild.sh` via
`docker compose exec -T api pytest backend/tests/test_rebuild_seed.py`.
"""
import base64

import pytest
import pytest_asyncio


# Module-local override of the conftest autouse `reset_settings` fixture.
# Without this, the autouse fixture runs BEFORE each test and would wipe
# the payload set by test_seed_all_fields before test_seed_logo uploads,
# leaving the post-seed state as defaults-plus-logo instead of seed-plus-logo.
# We ARE seeding the state intentionally; the rebuild assert stage verifies it.
@pytest_asyncio.fixture(autouse=True)
async def reset_settings():
    yield

# 1x1 opaque red PNG, base64-encoded then frozen here.
# Deterministic known-good PNG so the assert stage can compare bytes exactly.
RED_1X1_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)
RED_1X1_PNG: bytes = base64.b64decode(RED_1X1_PNG_B64)
assert RED_1X1_PNG[:8] == b"\x89PNG\r\n\x1a\n", "RED_1X1_PNG is not a valid PNG"

# D-specifics: 6 distinct oklch colors at 54° hue intervals for obvious diffs,
# plus app_name + default_language. Matches the backend oklch regex.
REBUILD_SEED_PAYLOAD = {
    "color_primary":     "oklch(0.5 0.2 30)",
    "color_accent":      "oklch(0.5 0.2 84)",
    "color_background":  "oklch(0.5 0.2 138)",
    "color_foreground":  "oklch(0.5 0.2 192)",
    "color_muted":       "oklch(0.5 0.2 246)",
    "color_destructive": "oklch(0.5 0.2 300)",
    "app_name":          "Rebuild Test Corp",
    "default_language":  "DE",
}

pytestmark = pytest.mark.asyncio


async def test_seed_all_fields(client):
    r = await client.put("/api/settings", json=REBUILD_SEED_PAYLOAD)
    assert r.status_code == 200, r.text
    body = r.json()
    for k, v in REBUILD_SEED_PAYLOAD.items():
        assert body[k] == v, f"{k}: expected {v!r}, got {body[k]!r}"


async def test_seed_logo(client):
    files = {"file": ("seed.png", RED_1X1_PNG, "image/png")}
    r = await client.post("/api/settings/logo", files=files)
    assert r.status_code == 200, r.text
    assert r.json().get("logo_url") is not None
