"""POST /api/upload-contacts — Kontakte ingestion + unmapped-token report."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.database import AsyncSessionLocal
from app.models import (
    PersonioEmployee,
    SalesContact,
    SalesEmployeeAlias,
)

pytestmark = pytest.mark.asyncio


def _hdr() -> bytes:
    return (
        b'="Datum"\t="Wer"\t="Typ"\t="Gruppe"\t="Sta"\t="Name"\t='
        b'"Kommentar"\t="VrgID"\r\n'
    )


async def _wipe() -> None:
    """Reset only the v1.41 tables; leave production personio_employees alone."""
    async with AsyncSessionLocal() as s:
        await s.execute(delete(SalesContact))
        await s.execute(delete(SalesEmployeeAlias))
        # Drop the synthetic test employee (id=9001) if a previous run left it.
        await s.execute(
            delete(PersonioEmployee).where(PersonioEmployee.id == 9001)
        )
        await s.commit()


async def test_kontakte_upload_inserts_and_reports_unmapped(admin_client):
    await _wipe()
    async with AsyncSessionLocal() as s:
        s.add(
            PersonioEmployee(
                id=9001,
                last_name="Karrer",
                synced_at=datetime.now(timezone.utc),
            )
        )
        s.add(
            SalesEmployeeAlias(
                personio_employee_id=9001,
                employee_token="KARRER",
                is_canonical=True,
            )
        )
        await s.commit()

    body = _hdr() + (
        b'08.02.2012\t="KARRER"\t="ERS"\t="L"\t1\t="Sonatech"\t='
        b'"Angebot 5000000"\t1\r\n'
        b'09.02.2012\t="UNKNOWN"\t="ORT"\t="L"\t1\t="ACME"\t="Visit"\t2\r\n'
    )
    r = await admin_client.post(
        "/api/upload-contacts",
        files={"file": ("kontakte.txt", body, "text/plain")},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["rows_inserted"] == 2
    assert any(t["token"] == "UNKNOWN" for t in payload["unmapped_tokens"])
    assert all(t["token"] != "KARRER" for t in payload["unmapped_tokens"])

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(SalesContact))).scalars().all()
        assert len(rows) == 2


async def test_kontakte_upload_replace_by_range_idempotent(admin_client):
    await _wipe()
    body1 = _hdr() + b'08.02.2012\t="X"\t="ERS"\t="L"\t1\t="A"\t="x"\t1\r\n'
    r1 = await admin_client.post(
        "/api/upload-contacts",
        files={"file": ("k.txt", body1, "text/plain")},
    )
    assert r1.status_code == 200
    assert r1.json()["rows_inserted"] == 1

    # Same date range, two rows → first row replaced, two inserted.
    body2 = _hdr() + (
        b'08.02.2012\t="X"\t="ERS"\t="L"\t1\t="A"\t="x"\t1\r\n'
        b'08.02.2012\t="Y"\t="ORT"\t="L"\t1\t="B"\t="y"\t2\r\n'
    )
    r2 = await admin_client.post(
        "/api/upload-contacts",
        files={"file": ("k.txt", body2, "text/plain")},
    )
    assert r2.status_code == 200
    assert r2.json()["rows_replaced"] == 1
    assert r2.json()["rows_inserted"] == 2

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(SalesContact))).scalars().all()
        assert len(rows) == 2


async def test_kontakte_upload_rejects_non_txt(admin_client):
    r = await admin_client.post(
        "/api/upload-contacts",
        files={"file": ("kontakte.csv", b"x", "text/csv")},
    )
    assert r.status_code == 422


async def test_kontakte_upload_admin_only(viewer_client):
    r = await viewer_client.post(
        "/api/upload-contacts",
        files={"file": ("k.txt", _hdr(), "text/plain")},
    )
    assert r.status_code in (401, 403)
