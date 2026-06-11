"""POST /api/upload-interessenten — Interessenten master-data ingestion."""
from datetime import date

import pytest
from sqlalchemy import delete, select

from app.database import AsyncSessionLocal
from app.models import Interessent, UploadBatch
from tests.test_interessenten_parser import _fixture, _row

pytestmark = pytest.mark.asyncio


async def _wipe() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Interessent))
        await s.execute(delete(UploadBatch))
        await s.commit()


async def test_upload_inserts_rows(admin_client):
    await _wipe()
    body = _fixture([
        _row("1", "Adria Airways", "22.09.2017"),
        _row("3", "Heinemann Aircraft", "13.10.2017"),
    ])
    r = await admin_client.post(
        "/api/upload-interessenten",
        files={"file": ("dev_excel_INT.txt", body, "text/plain")},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["rows_inserted"] == 2
    assert payload["rows_updated"] == 0

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(Interessent))).scalars().all()
        assert len(rows) == 2
        names = {r.name for r in rows}
        assert names == {"Adria Airways", "Heinemann Aircraft"}


async def test_upload_does_upsert_on_conflict(admin_client):
    await _wipe()
    # First upload — pure insert.
    body1 = _fixture([_row("1", "Old Name", "22.09.2017")])
    r1 = await admin_client.post(
        "/api/upload-interessenten",
        files={"file": ("a.txt", body1, "text/plain")},
    )
    assert r1.status_code == 200
    assert r1.json()["rows_inserted"] == 1

    # Re-upload with updated name+date → counts as 0 inserts, 1 update.
    body2 = _fixture([_row("1", "New Name", "01.06.2024")])
    r2 = await admin_client.post(
        "/api/upload-interessenten",
        files={"file": ("a.txt", body2, "text/plain")},
    )
    assert r2.status_code == 200
    payload = r2.json()
    assert payload["rows_inserted"] == 0
    assert payload["rows_updated"] == 1

    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(Interessent))).scalars().one()
        assert row.name == "New Name"
        assert row.datum_save == date(2024, 6, 1)


async def test_upload_rejects_non_txt(admin_client):
    r = await admin_client.post(
        "/api/upload-interessenten",
        files={"file": ("f.csv", b"x", "text/csv")},
    )
    assert r.status_code == 422


async def test_upload_admin_only(viewer_client):
    body = _fixture([_row("1", "Foo", "01.01.2024")])
    r = await viewer_client.post(
        "/api/upload-interessenten",
        files={"file": ("f.txt", body, "text/plain")},
    )
    assert r.status_code in (401, 403)
