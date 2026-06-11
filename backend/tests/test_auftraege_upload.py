"""POST /api/upload-auftraege — AswKpf_AUF.txt ingestion."""
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.database import AsyncSessionLocal
from app.models import Auftrag, UploadBatch
from tests.test_auftraege_parser import _fixture, _row

pytestmark = pytest.mark.asyncio


async def _wipe() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Auftrag))
        await s.execute(delete(UploadBatch))
        await s.commit()


async def test_upload_inserts_rows(admin_client):
    await _wipe()
    body = _fixture([
        _row("1023950", "02.01.2025", "ZETTLER", "1213,43"),
        _row("1023951", "03.01.2025", "HOHL", "5000"),
    ])
    r = await admin_client.post(
        "/api/upload-auftraege",
        files={"file": ("AswKpf_AUF.txt", body, "text/plain")},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["rows_inserted"] == 2
    assert payload["rows_updated"] == 0

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(Auftrag))).scalars().all()
        assert len(rows) == 2
        by_nr = {o.vorgang_nr: o for o in rows}
        assert by_nr["1023950"].wert_eur == Decimal("1213.43")
        assert by_nr["1023951"].erfasser == "HOHL"


async def test_upload_upserts_on_conflict(admin_client):
    await _wipe()
    body1 = _fixture([_row("9999", "01.01.2025", "ZETTLER", "100")])
    r1 = await admin_client.post(
        "/api/upload-auftraege",
        files={"file": ("a.txt", body1, "text/plain")},
    )
    assert r1.status_code == 200
    assert r1.json()["rows_inserted"] == 1

    body2 = _fixture([_row("9999", "02.01.2025", "HOHL", "500")])
    r2 = await admin_client.post(
        "/api/upload-auftraege",
        files={"file": ("a.txt", body2, "text/plain")},
    )
    assert r2.status_code == 200
    payload = r2.json()
    assert payload["rows_inserted"] == 0
    assert payload["rows_updated"] == 1

    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(Auftrag))).scalars().one()
        assert row.erfasser == "HOHL"
        assert row.wert_eur == Decimal("500")


async def test_upload_rejects_non_txt(admin_client):
    r = await admin_client.post(
        "/api/upload-auftraege",
        files={"file": ("f.csv", b"x", "text/csv")},
    )
    assert r.status_code == 422


async def test_upload_admin_only(viewer_client):
    body = _fixture([_row("1", "01.01.2025", "X", "100")])
    r = await viewer_client.post(
        "/api/upload-auftraege",
        files={"file": ("f.txt", body, "text/plain")},
    )
    assert r.status_code in (401, 403)
