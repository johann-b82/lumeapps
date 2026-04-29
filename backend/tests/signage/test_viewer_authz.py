"""AUTHZ-05 integration tests: Viewer JWT field-leak + signage mutation exclusions.

Validates:
- Viewer cannot read sensitive directus_users fields (tfa_secret, auth_data,
  external_identifier) — AUTHZ-03.
- Viewer gets 403 on every signage_* mutation attempt (POST/PATCH/DELETE) — AUTHZ-02.
- Viewer CAN read sales_records (read allowed) — AUTHZ-01 positive path.
- Viewer CAN read personio_employees without compute-only fields — AUTHZ-01 positive path.

Prerequisites: `docker compose up -d` — full stack with bootstrap-roles.sh applied.

Run:
    docker compose up -d
    pytest backend/tests/signage/test_viewer_authz.py -v
"""
from __future__ import annotations

import os

import httpx
import pytest
import pytest_asyncio

DIRECTUS_BASE_URL = os.environ.get("DIRECTUS_BASE_URL", "http://localhost:8055")
DIRECTUS_ADMIN_EMAIL = os.environ.get("DIRECTUS_ADMIN_EMAIL", "admin@example.com")
DIRECTUS_ADMIN_PASSWORD = os.environ.get("DIRECTUS_ADMIN_PASSWORD", "admin_test_pw")

# Seeded Viewer account — must exist after bootstrap-roles.sh runs.
# The bootstrap script creates the Viewer role; a Viewer user is seeded by the
# docker compose bootstrap-users service (or set via env for CI).
VIEWER_EMAIL = os.environ.get("VIEWER_EMAIL", "viewer@example.com")
VIEWER_PASSWORD = os.environ.get("VIEWER_PASSWORD", "viewer_test_pw")

# ---------------------------------------------------------------------------
# All signage_* collections that Viewer must NOT be able to mutate (AUTHZ-02).
# Source: 65-05-PLAN.md interfaces section + bootstrap-roles.sh section 5 comment.
# ---------------------------------------------------------------------------

SIGNAGE_COLLECTIONS = [
    "signage_devices",
    "signage_playlists",
    "signage_playlist_items",
    "signage_device_tags",
    "signage_playlist_tag_map",
    "signage_device_tag_map",
    "signage_schedules",
]

# A non-existent UUID for mutation targets — ensures we test auth, not business logic.
NONEXISTENT_UUID = "00000000-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def viewer_token() -> str:
    """Obtain a Viewer JWT via Directus /auth/login.

    The Viewer account must be seeded before this test runs (by bootstrap-users
    compose service or equivalent). If login fails, the fixture fails with a
    descriptive error.
    """
    resp = httpx.post(
        f"{DIRECTUS_BASE_URL}/auth/login",
        json={"email": VIEWER_EMAIL, "password": VIEWER_PASSWORD},
        timeout=15,
    )
    if resp.status_code != 200:
        pytest.fail(
            f"Viewer login failed (HTTP {resp.status_code}). "
            f"Ensure the Viewer account is seeded (email={VIEWER_EMAIL}). "
            f"Response: {resp.text[:300]}"
        )
    data = resp.json()
    token = data.get("data", {}).get("access_token") or data.get("access_token")
    if not token:
        pytest.fail(f"Could not parse access_token from Viewer login response: {data}")
    return token


@pytest_asyncio.fixture(scope="session")
async def viewer_directus_client(viewer_token: str) -> httpx.AsyncClient:
    """Return an async httpx client pre-configured with the Viewer Bearer token.

    Targets the Directus base URL directly (no FastAPI proxy).
    """
    async with httpx.AsyncClient(
        base_url=DIRECTUS_BASE_URL,
        headers={"Authorization": f"Bearer {viewer_token}"},
        timeout=15,
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# AUTHZ-03: Viewer must NOT leak sensitive directus_users fields
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_viewer_cannot_read_directus_users_secret_fields(
    viewer_directus_client: httpx.AsyncClient,
) -> None:
    """Viewer GET /users/me?fields=<sensitive> must not leak tfa_secret,
    auth_data, or external_identifier. Each field must be null/empty or absent.
    """
    r = await viewer_directus_client.get(
        "/users/me",
        params={"fields": "tfa_secret,auth_data,external_identifier"},
    )
    # Directus may return 200 with null values or 403 if field-level blocked.
    assert r.status_code in (200, 403), (
        f"unexpected status {r.status_code} reading /users/me sensitive fields"
    )
    if r.status_code == 200:
        body = r.json().get("data", {})
        assert body.get("tfa_secret") in (None, ""), (
            f"tfa_secret LEAKED: {body.get('tfa_secret')!r}"
        )
        assert body.get("auth_data") in (None, ""), (
            f"auth_data LEAKED: {body.get('auth_data')!r}"
        )
        assert body.get("external_identifier") in (None, ""), (
            f"external_identifier LEAKED: {body.get('external_identifier')!r}"
        )


# ---------------------------------------------------------------------------
# AUTHZ-02: Viewer must NOT be able to mutate any signage_* collection
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize("collection", SIGNAGE_COLLECTIONS)
@pytest.mark.asyncio
async def test_viewer_cannot_mutate_signage_collection(
    collection: str,
    viewer_directus_client: httpx.AsyncClient,
) -> None:
    """Viewer POST/PATCH/DELETE on signage_* must return 403.
    PATCH/DELETE against a non-existent UUID may return 403 or 404 — both accepted
    (resource not found is a valid response before or after auth check).
    """
    # POST — create attempt
    post_r = await viewer_directus_client.post(
        f"/items/{collection}",
        json={},
    )
    assert post_r.status_code == 403, (
        f"expected 403 on POST /items/{collection}, got {post_r.status_code}"
    )

    # PATCH — update attempt on a non-existent item
    patch_r = await viewer_directus_client.patch(
        f"/items/{collection}/{NONEXISTENT_UUID}",
        json={"name": "attempted-mutation"},
    )
    assert patch_r.status_code in (403, 404), (
        f"expected 403 or 404 on PATCH /items/{collection}/{NONEXISTENT_UUID}, "
        f"got {patch_r.status_code}"
    )

    # DELETE — delete attempt on a non-existent item
    delete_r = await viewer_directus_client.delete(
        f"/items/{collection}/{NONEXISTENT_UUID}",
    )
    assert delete_r.status_code in (403, 404), (
        f"expected 403 or 404 on DELETE /items/{collection}/{NONEXISTENT_UUID}, "
        f"got {delete_r.status_code}"
    )


# ---------------------------------------------------------------------------
# AUTHZ-01: Viewer CAN read sales_records (positive test)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_viewer_can_read_sales_records(
    viewer_directus_client: httpx.AsyncClient,
) -> None:
    """Viewer GET /items/sales_records must return 200.
    Validates AUTHZ-01 positive path — Viewer is allowed to read sales data.
    """
    r = await viewer_directus_client.get(
        "/items/sales_records",
        params={"limit": 1},
    )
    assert r.status_code == 200, (
        f"Viewer expected 200 on GET /items/sales_records, got {r.status_code}: {r.text[:200]}"
    )


# ---------------------------------------------------------------------------
# AUTHZ-01: Viewer CAN read personio_employees (without compute-derived fields)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_viewer_can_read_personio_employees_without_compute_fields(
    viewer_directus_client: httpx.AsyncClient,
) -> None:
    """Viewer GET /items/personio_employees must return 200 for column-backed fields.
    Compute-derived fields (total_hours, overtime_hours, overtime_ratio) are not
    in the allowlist — requesting them should produce null or absent fields, not a leak.
    """
    # Positive: column-backed fields should be readable
    r = await viewer_directus_client.get(
        "/items/personio_employees",
        params={"limit": 1, "fields": "id,first_name,last_name,status,department"},
    )
    assert r.status_code == 200, (
        f"Viewer expected 200 on GET /items/personio_employees (column-backed fields), "
        f"got {r.status_code}: {r.text[:200]}"
    )

    # Compute-derived field: total_hours is NOT in the Directus allowlist.
    # Requesting it should return null/absent — not a real value from the DB column.
    r2 = await viewer_directus_client.get(
        "/items/personio_employees",
        params={"limit": 1, "fields": "total_hours"},
    )
    # Directus may return 200 with null field or 403 — either is acceptable.
    assert r2.status_code in (200, 403), (
        f"unexpected status {r2.status_code} on total_hours field request"
    )
    if r2.status_code == 200:
        data = r2.json().get("data", [])
        if data:
            assert data[0].get("total_hours") in (None, ""), (
                f"compute-derived total_hours leaked to Viewer: {data[0].get('total_hours')!r}"
            )
