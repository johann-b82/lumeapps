"""POST /api/upload-umsatz — AswKpf_RG.txt ingestion."""
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.database import AsyncSessionLocal
from app.models import Revenue, UploadBatch
from tests.test_revenue_parser import _fixture, _row

pytestmark = pytest.mark.asyncio


async def _wipe() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Revenue))
        await s.execute(delete(UploadBatch))
        await s.commit()


async def test_upload_inserts_RG_and_GS(admin_client):
    await _wipe()
    body = _fixture([
        _row("RG", "3030989", "07.01.2025", "255,6"),
        _row("GS", "3030988", "07.01.2025", "-332,48"),
    ])
    r = await admin_client.post(
        "/api/upload-umsatz",
        files={"file": ("AswKpf_RG.txt", body, "text/plain")},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["rows_inserted"] == 2
    assert payload["rows_updated"] == 0

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(Revenue))).scalars().all()
        assert len(rows) == 2
        nrs = {r.vorgang_nr for r in rows}
        assert nrs == {"3030989", "3030988"}
        gs = next(r for r in rows if r.typ == "GS")
        assert gs.wert_eur == Decimal("-332.48")


async def test_upload_upserts_on_conflict(admin_client):
    await _wipe()
    body1 = _fixture([_row("RG", "9", "01.01.2025", "100")])
    r1 = await admin_client.post(
        "/api/upload-umsatz",
        files={"file": ("a.txt", body1, "text/plain")},
    )
    assert r1.status_code == 200
    assert r1.json()["rows_inserted"] == 1

    body2 = _fixture([_row("GS", "9", "02.01.2025", "-50")])
    r2 = await admin_client.post(
        "/api/upload-umsatz",
        files={"file": ("a.txt", body2, "text/plain")},
    )
    assert r2.status_code == 200
    payload = r2.json()
    assert payload["rows_inserted"] == 0
    assert payload["rows_updated"] == 1

    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(Revenue))).scalars().one()
        assert row.typ == "GS"
        assert row.wert_eur == Decimal("-50")


async def test_upload_rejects_non_txt(admin_client):
    r = await admin_client.post(
        "/api/upload-umsatz",
        files={"file": ("f.csv", b"x", "text/csv")},
    )
    assert r.status_code == 422


async def test_upload_admin_only(viewer_client):
    body = _fixture([_row("RG", "1", "01.01.2025", "100")])
    r = await viewer_client.post(
        "/api/upload-umsatz",
        files={"file": ("f.txt", body, "text/plain")},
    )
    assert r.status_code in (401, 403)
