"""Integration tests for /api/settings/* — covers roadmap success criteria 1-4.

Success criterion 5 (docker compose up --build persistence) is covered by
Plan 06's explicit docker verification script.
"""
import pytest

from app.defaults import DEFAULT_SETTINGS
from app.security.logo_validation import PNG_SIGNATURE

pytestmark = pytest.mark.asyncio

VALID_PAYLOAD = {
    **DEFAULT_SETTINGS,
    "app_name": "My Brand",
}

MINIMAL_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    b'<circle cx="5" cy="5" r="4"></circle>'
    b'</svg>'
)

# Smallest "valid-enough" PNG: signature + some padding. sniff_mime only
# checks the 8-byte signature — no full PNG parser in v1.1 (D-14).
FAKE_PNG = PNG_SIGNATURE + b"\x00" * 100


# --- Success Criterion 1 -------------------------------------------------

async def test_get_settings_returns_shape(client):
    r = await client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "color_primary", "color_accent", "color_background",
        "color_foreground", "color_muted", "color_destructive",
        "app_name", "default_language", "logo_url", "logo_updated_at",
    ):
        assert key in body, f"missing key: {key}"
    assert body["logo_url"] is None
    assert body["logo_updated_at"] is None
    assert body["app_name"] == DEFAULT_SETTINGS["app_name"]


# --- Success Criterion 2 -------------------------------------------------

async def test_put_rejects_semicolon_in_color(client):
    bad = {**VALID_PAYLOAD, "color_primary": "oklch(0.5 0.15 250); background: red"}
    r = await client.put("/api/settings", json=bad)
    assert r.status_code == 422


async def test_put_rejects_url_function_in_color(client):
    bad = {**VALID_PAYLOAD, "color_primary": "oklch(0.5 0.15 url(evil))"}
    r = await client.put("/api/settings", json=bad)
    assert r.status_code == 422


async def test_put_valid_payload_updates_row(client):
    r = await client.put("/api/settings", json=VALID_PAYLOAD)
    assert r.status_code == 200
    body = r.json()
    assert body["app_name"] == "My Brand"
    assert body["color_primary"] == DEFAULT_SETTINGS["color_primary"]


# --- Success Criterion 3 -------------------------------------------------

async def test_logo_svg_with_script_rejected(client):
    evil = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    r = await client.post(
        "/api/settings/logo",
        files={"file": ("evil.svg", evil, "image/svg+xml")},
    )
    assert r.status_code == 422
    # Confirm nothing was stored
    r2 = await client.get("/api/settings")
    assert r2.json()["logo_url"] is None


# --- Success Criterion 4 -------------------------------------------------

async def test_put_defaults_resets_logo(client):
    # 1. Upload a valid SVG logo
    up = await client.post(
        "/api/settings/logo",
        files={"file": ("logo.svg", MINIMAL_SVG, "image/svg+xml")},
    )
    assert up.status_code == 200
    assert up.json()["logo_url"] is not None

    # 2. PUT canonical defaults -> logo should be cleared (D-07 full reset)
    r = await client.put("/api/settings", json=DEFAULT_SETTINGS)
    assert r.status_code == 200
    body = r.json()
    assert body["logo_url"] is None
    assert body["app_name"] == DEFAULT_SETTINGS["app_name"]
    assert body["color_primary"] == DEFAULT_SETTINGS["color_primary"]


# --- Logo upload: happy paths and edge cases ----------------------------

async def test_post_logo_png_happy_path(client):
    r = await client.post(
        "/api/settings/logo",
        files={"file": ("logo.png", FAKE_PNG, "image/png")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["logo_url"] is not None
    assert body["logo_url"].startswith("/api/settings/logo?v=")


async def test_post_logo_svg_happy_path(client):
    r = await client.post(
        "/api/settings/logo",
        files={"file": ("logo.svg", MINIMAL_SVG, "image/svg+xml")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["logo_url"] is not None


async def test_post_logo_wrong_extension_rejected(client):
    r = await client.post(
        "/api/settings/logo",
        files={"file": ("logo.gif", b"GIF89a...", "image/gif")},
    )
    assert r.status_code == 422


async def test_post_logo_oversize_rejected(client):
    oversize = PNG_SIGNATURE + b"\x00" * (1024 * 1024)  # 1 MB + 8 signature bytes
    r = await client.post(
        "/api/settings/logo",
        files={"file": ("big.png", oversize, "image/png")},
    )
    assert r.status_code == 422


async def test_post_logo_svg_extension_but_png_bytes_rejected(client):
    # sniff_mime detects the mismatch
    r = await client.post(
        "/api/settings/logo",
        files={"file": ("fake.svg", FAKE_PNG, "image/svg+xml")},
    )
    assert r.status_code == 422


# --- GET /api/settings/logo ---------------------------------------------

async def test_get_logo_404_when_unset(client):
    r = await client.get("/api/settings/logo")
    assert r.status_code == 404


async def test_get_logo_returns_bytes_and_etag(client):
    await client.post(
        "/api/settings/logo",
        files={"file": ("logo.png", FAKE_PNG, "image/png")},
    )
    r = await client.get("/api/settings/logo")
    assert r.status_code == 200
    assert r.content == FAKE_PNG
    assert r.headers["content-type"].startswith("image/png")
    assert r.headers["etag"].startswith('W/"')
    assert "cache-control" in r.headers


async def test_get_logo_304_on_matching_if_none_match(client):
    await client.post(
        "/api/settings/logo",
        files={"file": ("logo.png", FAKE_PNG, "image/png")},
    )
    first = await client.get("/api/settings/logo")
    etag = first.headers["etag"]
    second = await client.get(
        "/api/settings/logo",
        headers={"If-None-Match": etag},
    )
    assert second.status_code == 304
    assert second.headers["etag"] == etag
