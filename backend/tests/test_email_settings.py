"""Settings read/write coverage for the v1.82 Office 365 e-mail fields.

The client secret is write-only: PUT accepts `email_client_secret`, GET/PUT
responses expose only `email_has_secret`. None/omitted means "don't change",
mirroring the Personio / World Cup / ATR credential pattern.
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
async def test_email_settings_roundtrip(admin_client):
    payload = await _core_payload(admin_client)
    payload.update(
        email_tenant_id="tenant-1",
        email_client_id="client-1",
        email_client_secret="s3cr3t",
        email_sender_address="noreply@firma.de",
        email_sender_name="LumeApps",
        email_enabled=True,
    )
    r = await admin_client.put("/api/settings", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["email_tenant_id"] == "tenant-1"
    assert body["email_client_id"] == "client-1"
    assert body["email_sender_address"] == "noreply@firma.de"
    assert body["email_sender_name"] == "LumeApps"
    assert body["email_enabled"] is True
    assert body["email_has_secret"] is True
    assert "email_client_secret" not in body  # never echo the secret


@pytest.mark.asyncio
async def test_email_secret_preserved_when_omitted(admin_client):
    payload = await _core_payload(admin_client)
    r = await admin_client.put(
        "/api/settings", json={**payload, "email_client_secret": "abc"}
    )
    assert r.json()["email_has_secret"] is True
    # PUT without the secret field must not clear the stored secret.
    r2 = await admin_client.put("/api/settings", json=payload)
    assert r2.json()["email_has_secret"] is True


@pytest.mark.asyncio
async def test_email_enabled_toggle(admin_client):
    """email_enabled can be turned on and back off via PUT."""
    payload = await _core_payload(admin_client)
    on = await admin_client.put("/api/settings", json={**payload, "email_enabled": True})
    assert on.json()["email_enabled"] is True
    off = await admin_client.put("/api/settings", json={**payload, "email_enabled": False})
    assert off.json()["email_enabled"] is False


@pytest.mark.asyncio
async def test_email_auth_mode_switch(admin_client):
    """email_auth_mode switches between 'app' and 'delegated' via PUT."""
    payload = await _core_payload(admin_client)
    r = await admin_client.put("/api/settings", json={**payload, "email_auth_mode": "delegated"})
    body = r.json()
    assert body["email_auth_mode"] == "delegated"
    r2 = await admin_client.put("/api/settings", json={**payload, "email_auth_mode": "app"})
    assert r2.json()["email_auth_mode"] == "app"


@pytest.mark.asyncio
async def test_email_auth_mode_rejects_bad_value(admin_client):
    payload = await _core_payload(admin_client)
    r = await admin_client.put("/api/settings", json={**payload, "email_auth_mode": "smtp"})
    assert r.status_code == 422
