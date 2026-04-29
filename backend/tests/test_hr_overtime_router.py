"""Phase 67-01 MIG-DATA-03 — hr_overtime router shape + validation tests.

These tests assert wiring + FastAPI native 422 behavior for the new
`/api/data/employees/overtime` endpoint. Compute-loop arithmetic is
exercised in higher-level test fixtures once the DB-backed harness
arrives in later plans (Plan 02/03 frontend integration).
"""
import pytest
from httpx import ASGITransport, AsyncClient

from tests.test_directus_auth import ADMIN_UUID, _mint


def test_router_module_imports_with_expected_route():
    from app.routers.hr_overtime import router

    assert router.prefix == "/api/data"
    paths = [r.path for r in router.routes]
    assert "/api/data/employees/overtime" in paths, paths


@pytest.mark.asyncio
async def test_missing_date_from_returns_422():
    from app.main import app

    token = _mint(ADMIN_UUID)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            "/api/data/employees/overtime",
            params={"date_to": "2026-04-30"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_missing_date_to_returns_422():
    from app.main import app

    token = _mint(ADMIN_UUID)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            "/api/data/employees/overtime",
            params={"date_from": "2026-04-01"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_missing_both_dates_returns_422():
    from app.main import app

    token = _mint(ADMIN_UUID)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            "/api/data/employees/overtime",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_inverted_range_returns_422_with_detail():
    from app.main import app

    token = _mint(ADMIN_UUID)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            "/api/data/employees/overtime",
            params={"date_from": "2026-04-30", "date_to": "2026-04-01"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 422, r.text
    assert r.json() == {"detail": "date_from must be <= date_to"}


@pytest.mark.asyncio
async def test_unauthenticated_returns_401():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            "/api/data/employees/overtime",
            params={"date_from": "2026-04-01", "date_to": "2026-04-30"},
        )
    assert r.status_code == 401, r.text
