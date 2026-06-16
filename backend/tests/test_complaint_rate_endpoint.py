"""Customer-complaint rate endpoints (v1.58).

These tests WIPE quality_records and delivery_records — run them only
against a disposable test DB. The session conftest's `admin_client`
fixture already mints the auth token; we just need clean tables.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

import openpyxl
import pytest
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models import DeliveryRecord, QualityRecord, UploadBatch

pytestmark = pytest.mark.asyncio


_8D_HEADER = (
    "Nr.\tDatum\tAussteller\tAdress Nr.\tAdressen\tArtikel\tBezeichnung\t"
    "Status\tgelöscht\tArt\tMenge\takzeptierte Menge\r\n"
)


def _build_8d(rows: list[str]) -> bytes:
    return (_8D_HEADER + "".join(rows)).encode("cp1252")


_LS_HEADER = [
    "Typ", "Vorgang Nr.", "Pos", "UPos", "Datum", "Adr Nr.", "Name 1",
    "Ort", "Artnr", "Version", "Bezeichnung 1", "Menge", "ME", "St",
    "Lieferdatum", "Preis", "Pos Wert", "Pos Typ 2", "Fremdnr",
    "Sperre manuell", "Sperre K-Limit", "Auftrag", "Pos.1",
]


def _build_ls(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(_LS_HEADER)
    for r in rows:
        ws.append(list(r) + [None] * (len(_LS_HEADER) - len(r)))
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _wipe() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(QualityRecord))
        await s.execute(delete(DeliveryRecord))
        await s.execute(
            delete(UploadBatch).where(UploadBatch.kind.in_(("quality", "deliveries")))
        )
        await s.commit()


async def _seed_quality(admin_client, rows: list[str]) -> None:
    body = _build_8d(rows)
    r = await admin_client.post(
        "/api/upload-quality",
        files={"file": ("8D.txt", body, "text/plain")},
    )
    assert r.status_code == 200, r.text


async def _seed_deliveries(admin_client, rows: list[list]) -> None:
    body = _build_ls(rows)
    r = await admin_client.post(
        "/api/upload-deliveries",
        files={"file": ("LS.xlsx", body, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Delivery upload smoke
# ---------------------------------------------------------------------------


async def test_upload_deliveries_inserts_rows(admin_client):
    await _wipe()
    body = _build_ls([
        ["LS", "1000", 1, 0, "2026-02-01", "10", "X", "C", "A", None,
         "x", 100, "STK", 1, "2026-02-01", 1, 100, "AB", "ext", "N", 0,
         "ord", 1],
    ])
    r = await admin_client.post(
        "/api/upload-deliveries",
        files={"file": ("LS.xlsx", body, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["rows_inserted"] == 1
    assert payload["rows_updated"] == 0


async def test_upload_deliveries_reupload_updates(admin_client):
    """Same composite key, different qty → row updated, not duplicated."""
    await _wipe()
    await _seed_deliveries(admin_client, [
        ["LS", "2000", 1, 0, "2026-02-01", "10", "X", "C", "A", None,
         "x", 100, "STK", 1, "2026-02-01", 1, 100, "AB", "ext", "N", 0,
         "ord", 1],
    ])
    body = _build_ls([
        ["LS", "2000", 1, 0, "2026-02-01", "10", "X", "C", "A", None,
         "x", 250, "STK", 1, "2026-02-01", 1, 250, "AB", "ext", "N", 0,
         "ord", 1],
    ])
    r = await admin_client.post(
        "/api/upload-deliveries",
        files={"file": ("LS.xlsx", body, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.json()["rows_inserted"] == 0
    assert r.json()["rows_updated"] == 1

    from sqlalchemy import select
    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(select(DeliveryRecord).where(DeliveryRecord.vorgang_nr == "2000"))
        ).scalar_one()
        assert row.quantity == Decimal("250")


# ---------------------------------------------------------------------------
# Complaint rate KPI
# ---------------------------------------------------------------------------


async def test_complaint_rate_uses_total_qty_by_default(admin_client):
    await _wipe()
    # Deliveries: 1000 units in April.
    await _seed_deliveries(admin_client, [
        ["LS", "3000", 1, 0, "2026-04-01", "10", "X", "C", "A", None,
         "x", 1000, "STK", 1, "2026-04-01", 1, 1000, "AB", "ext", "N", 0,
         "ord", 1],
    ])
    # Complaints: one KUNRE for 25 (accepted 20), one KUN RE for 7.
    await _seed_quality(admin_client, [
        "9001\t05.04.2026\tBROSE\t12\tACME\tReklamation\tDummy\tisignal_flag_red\tN\tKUNRE\t25\t20\r\n",
        "9002\t06.04.2026\tBROSE\t12\tACME\tReklamation\tDummy\tisignal_flag_red\tN\tKUN RE\t7\t5\r\n",
    ])

    r = await admin_client.get(
        "/api/quality/complaint-rate?date_from=2026-04-01&date_to=2026-04-30"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Both KUNRE variants counted → 25 + 7 = 32 over 1000 delivered.
    assert body["complaint_qty"] == 32
    assert body["delivered_qty"] == 1000
    assert abs(body["rate"] - 0.032) < 1e-9


async def test_complaint_rate_accepted_qty_mode(admin_client):
    await _wipe()
    await _seed_deliveries(admin_client, [
        ["LS", "4000", 1, 0, "2026-04-01", "10", "X", "C", "A", None,
         "x", 1000, "STK", 1, "2026-04-01", 1, 1000, "AB", "ext", "N", 0,
         "ord", 1],
    ])
    await _seed_quality(admin_client, [
        "9101\t05.04.2026\tBROSE\t12\tACME\tReklamation\tDummy\tisignal_flag_red\tN\tKUNRE\t25\t20\r\n",
        "9102\t06.04.2026\tBROSE\t12\tACME\tReklamation\tDummy\tisignal_flag_red\tN\tKUN RE\t7\t5\r\n",
    ])

    r = await admin_client.get(
        "/api/quality/complaint-rate"
        "?date_from=2026-04-01&date_to=2026-04-30&qty_mode=accepted"
    )
    body = r.json()
    # accepted: 20 + 5 = 25.
    assert body["complaint_qty"] == 25
    assert abs(body["rate"] - 0.025) < 1e-9


async def test_complaint_rate_zero_deliveries_returns_null_rate(admin_client):
    await _wipe()
    # Complaint without deliveries → rate undefined (must be null, never inf).
    await _seed_quality(admin_client, [
        "9201\t05.04.2026\tBROSE\t12\tACME\tReklamation\tDummy\tisignal_flag_red\tN\tKUNRE\t10\t10\r\n",
    ])
    r = await admin_client.get(
        "/api/quality/complaint-rate?date_from=2026-04-01&date_to=2026-04-30"
    )
    body = r.json()
    assert body["rate"] is None
    assert body["complaint_qty"] == 10
    assert body["delivered_qty"] == 0


async def test_complaint_rate_rejects_unknown_qty_mode(admin_client):
    r = await admin_client.get(
        "/api/quality/complaint-rate"
        "?date_from=2026-04-01&date_to=2026-04-30&qty_mode=bogus"
    )
    assert r.status_code == 400


async def test_complaints_list_filters_to_kunre_variants_only(admin_client):
    await _wipe()
    await _seed_quality(admin_client, [
        "9301\t05.04.2026\t\t\t\tFinding\tA\tx\tN\tKU AUD\t1\t1\r\n",
        "9302\t06.04.2026\t\t\t\tReklamation\tB\ty\tN\tKUNRE\t2\t2\r\n",
        "9303\t07.04.2026\t\t\t\tReklamation\tC\tz\tN\tKUN RE\t3\t3\r\n",
        "9304\t08.04.2026\t\t\t\tReklamation\tD\tw\tN\tLIE RE\t4\t4\r\n",
    ])
    r = await admin_client.get(
        "/api/quality/complaints/list"
        "?date_from=2026-04-01&date_to=2026-04-30"
    )
    rows = r.json()
    assert {row["report_nr"] for row in rows} == {"9302", "9303"}
