"""Manual sales-rep alias CRUD endpoints."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models import PersonioEmployee, SalesEmployeeAlias

pytestmark = pytest.mark.asyncio


async def _wipe() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(SalesEmployeeAlias))
        await s.execute(
            delete(PersonioEmployee).where(PersonioEmployee.id.in_([90011, 90012]))
        )
        await s.commit()


async def test_list_create_delete_roundtrip(admin_client):
    await _wipe()
    async with AsyncSessionLocal() as s:
        s.add(
            PersonioEmployee(
                id=90011,
                last_name="Müller",
                synced_at=datetime.now(timezone.utc),
            )
        )
        await s.commit()

    r = await admin_client.post(
        "/api/admin/sales-aliases",
        json={"personio_employee_id": 90011, "employee_token": "guenni"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["employee_token"] == "GUENNI"
    assert body["is_canonical"] is False
    alias_id = body["id"]

    r2 = await admin_client.get("/api/admin/sales-aliases")
    assert r2.status_code == 200
    assert any(a["id"] == alias_id for a in r2.json())

    r3 = await admin_client.delete(f"/api/admin/sales-aliases/{alias_id}")
    assert r3.status_code == 204


async def test_create_rejects_duplicate_token(admin_client):
    await _wipe()
    async with AsyncSessionLocal() as s:
        s.add(
            PersonioEmployee(
                id=90011,
                last_name="X",
                synced_at=datetime.now(timezone.utc),
            )
        )
        s.add(
            SalesEmployeeAlias(
                personio_employee_id=90011,
                employee_token="DUP",
                is_canonical=False,
            )
        )
        await s.commit()
    r = await admin_client.post(
        "/api/admin/sales-aliases",
        json={"personio_employee_id": 90011, "employee_token": "DUP"},
    )
    assert r.status_code == 409


async def test_cannot_delete_canonical_alias(admin_client):
    await _wipe()
    async with AsyncSessionLocal() as s:
        s.add(
            PersonioEmployee(
                id=90011,
                last_name="X",
                synced_at=datetime.now(timezone.utc),
            )
        )
        s.add(
            SalesEmployeeAlias(
                id=42,
                personio_employee_id=90011,
                employee_token="X",
                is_canonical=True,
            )
        )
        await s.commit()
    r = await admin_client.delete("/api/admin/sales-aliases/42")
    assert r.status_code == 409


async def test_admin_only(viewer_client):
    r = await viewer_client.get("/api/admin/sales-aliases")
    assert r.status_code in (401, 403)
