"""POST /api/upload-angebote — AswKpf_ANG.txt ingestion."""
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.database import AsyncSessionLocal
from app.models import Offer, UploadBatch
from tests.test_angebote_parser import _fixture, _row

pytestmark = pytest.mark.asyncio


async def _wipe() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Offer))
        await s.execute(delete(UploadBatch))
        await s.commit()


async def test_upload_inserts_rows(admin_client):
    await _wipe()
    body = _fixture([
        _row("5002640", "22.01.2026", "SCHMIDT", "322611,16"),
        _row("5002641", "19.01.2026", "SCHMIDT", "84000"),
    ])
    r = await admin_client.post(
        "/api/upload-angebote",
        files={"file": ("AswKpf_ANG.txt", body, "text/plain")},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["rows_inserted"] == 2
    assert payload["rows_updated"] == 0

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(Offer))).scalars().all()
        assert len(rows) == 2
        by_nr = {o.vorgang_nr: o for o in rows}
        assert by_nr["5002640"].wert_eur == Decimal("322611.16")
        assert by_nr["5002641"].wert_eur == Decimal("84000")


async def test_upload_upserts_on_conflict(admin_client):
    await _wipe()
    body1 = _fixture([_row("9999", "01.01.2026", "SCHMIDT", "100")])
    r1 = await admin_client.post(
        "/api/upload-angebote",
        files={"file": ("a.txt", body1, "text/plain")},
    )
    assert r1.status_code == 200
    assert r1.json()["rows_inserted"] == 1

    body2 = _fixture([_row("9999", "02.01.2026", "HOHL", "500")])
    r2 = await admin_client.post(
        "/api/upload-angebote",
        files={"file": ("a.txt", body2, "text/plain")},
    )
    assert r2.status_code == 200
    payload = r2.json()
    assert payload["rows_inserted"] == 0
    assert payload["rows_updated"] == 1

    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(Offer))).scalars().one()
        assert row.erfasser == "HOHL"
        assert row.wert_eur == Decimal("500")


async def test_upload_rejects_non_txt(admin_client):
    r = await admin_client.post(
        "/api/upload-angebote",
        files={"file": ("f.csv", b"x", "text/csv")},
    )
    assert r.status_code == 422


async def test_upload_admin_only(viewer_client):
    body = _fixture([_row("1", "01.01.2026", "X", "100")])
    r = await viewer_client.post(
        "/api/upload-angebote",
        files={"file": ("f.txt", body, "text/plain")},
    )
    assert r.status_code in (401, 403)
