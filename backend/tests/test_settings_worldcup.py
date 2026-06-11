"""Settings read/write coverage for the World Cup signage fields (v1.57).

The API key is write-only: PUT accepts `worldcup_api_key`, GET/PUT responses
expose only `worldcup_has_api_key`. None/omitted means "don't change",
mirroring the Personio credential pattern.
"""
import pytest

_CORE = [
    "color_primary",
    "color_accent",
    "color_background",
    "color_foreground",
    "color_muted",
    "color_destructive",
    "app_name",
]


async def _core_payload(client) -> dict:
    base = (await client.get("/api/settings")).json()
    return {k: base[k] for k in _CORE}


@pytest.mark.asyncio
async def test_worldcup_settings_roundtrip(admin_client):
    payload = await _core_payload(admin_client)
    payload["worldcup_api_key"] = "test-key-123"
    payload["worldcup_refresh_seconds"] = 120
    r = await admin_client.put("/api/settings", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["worldcup_has_api_key"] is True
    assert body["worldcup_refresh_seconds"] == 120
    assert "worldcup_api_key" not in body  # never echo the key


@pytest.mark.asyncio
async def test_worldcup_refresh_bounds(admin_client):
    payload = await _core_payload(admin_client)
    for bad in (10, 5000):
        r = await admin_client.put(
            "/api/settings", json={**payload, "worldcup_refresh_seconds": bad}
        )
        assert r.status_code == 422, f"expected 422 for {bad}"


@pytest.mark.asyncio
async def test_worldcup_key_preserved_when_omitted(admin_client):
    payload = await _core_payload(admin_client)
    r = await admin_client.put(
        "/api/settings", json={**payload, "worldcup_api_key": "k1"}
    )
    assert r.json()["worldcup_has_api_key"] is True
    # PUT without the key field must not clear the stored key.
    r2 = await admin_client.put("/api/settings", json=payload)
    assert r2.json()["worldcup_has_api_key"] is True
