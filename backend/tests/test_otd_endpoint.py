"""Einkauf / OTD (Liefertermintreue) endpoints (v1.60).

These tests WIPE delivery_reliability — run only against a disposable test
DB (acm_kpi_test), never the live acm_kpi database.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models import DeliveryReliabilityRecord, UploadBatch

pytestmark = pytest.mark.asyncio


_HEADER = [
    "Auftrag", "Pos", "UPos", "Kunde", "geliefert", "Lieferdatum",
    "Verzug (Tage)", "Artikel", "Bezeichnung", "ME", "Menge", "Kundennummer",
]
_TITLE = "Auswertung:\tLiefertreue (von 01.04.2026 bis 30.04.2026)"


def _build_otd(rows: list[dict], *, title: bool = True) -> bytes:
    lines: list[str] = []
    if title:
        lines.append(_TITLE)
    lines.append("\t".join(_HEADER))
    for r in rows:
        lines.append("\t".join(str(r.get(h, "")) for h in _HEADER))
    return ("\r\n".join(lines) + "\r\n").encode("cp1252")


def _r(auftrag, verzug, geliefert, *, menge="10", kunde="ACME", adr="81105"):
    return {
        "Auftrag": auftrag, "Pos": "1", "UPos": "0", "Kunde": kunde,
        "geliefert": geliefert, "Lieferdatum": "01.04.2026",
        "Verzug (Tage)": verzug, "Artikel": "L1", "Bezeichnung": "x",
        "ME": "STK", "Menge": menge, "Kundennummer": adr,
    }


async def _wipe() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(DeliveryReliabilityRecord))
        await s.execute(
            delete(UploadBatch).where(UploadBatch.kind == "delivery_reliability")
        )
        await s.commit()


async def _seed(admin_client, rows: list[dict], *, title: bool = True):
    body = _build_otd(rows, title=title)
    r = await admin_client.post(
        "/api/upload-delivery-reliability",
        files={"file": ("OTD.txt", body, "text/plain")},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


async def test_upload_inserts_rows_and_reports_period(admin_client):
    await _wipe()
    payload = await _seed(admin_client, [_r("A1", "0", "05.04.2026")])
    assert payload["rows_inserted"] == 1
    assert payload["rows_updated"] == 0
    assert payload["period_from"] == "2026-04-01"
    assert payload["period_to"] == "2026-04-30"


async def test_reupload_updates_same_key(admin_client):
    await _wipe()
    await _seed(admin_client, [_r("A2", "0", "05.04.2026")])
    payload = await _seed(admin_client, [_r("A2", "9", "05.04.2026")])
    assert payload["rows_inserted"] == 0
    assert payload["rows_updated"] == 1

    from sqlalchemy import select
    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(
                select(DeliveryReliabilityRecord).where(
                    DeliveryReliabilityRecord.auftrag == "A2"
                )
            )
        ).scalar_one()
        assert row.verzug_tage == 9


# ---------------------------------------------------------------------------
# OTD KPI
# ---------------------------------------------------------------------------


async def test_otd_rate_is_punctual_over_total(admin_client):
    await _wipe()
    await _seed(admin_client, [
        _r("P1", "-2", "05.04.2026"),  # early  -> punctual
        _r("P2", "0", "10.04.2026"),   # on day -> punctual
        _r("P3", "5", "15.04.2026"),   # late   -> not punctual
    ])
    r = await admin_client.get(
        "/api/procurement/otd?date_from=2026-04-01&date_to=2026-04-30"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_count"] == 3
    assert body["punctual_count"] == 2
    assert abs(body["rate"] - (2 / 3)) < 1e-9
    assert abs(body["avg_delay"] - 1.0) < 1e-9  # (-2 + 0 + 5) / 3


async def test_otd_window_filters_by_geliefert(admin_client):
    await _wipe()
    await _seed(admin_client, [
        _r("W1", "0", "10.04.2026"),   # inside April
        _r("W2", "0", "05.05.2026"),   # outside April
    ])
    r = await admin_client.get(
        "/api/procurement/otd?date_from=2026-04-01&date_to=2026-04-30"
    )
    body = r.json()
    assert body["total_count"] == 1
    assert body["punctual_count"] == 1


async def test_otd_empty_window_returns_null_rate(admin_client):
    await _wipe()
    await _seed(admin_client, [_r("E1", "0", "05.04.2026")])
    r = await admin_client.get(
        "/api/procurement/otd?date_from=2026-01-01&date_to=2026-01-31"
    )
    body = r.json()
    assert body["rate"] is None
    assert body["total_count"] == 0


async def test_otd_list_returns_positions(admin_client):
    await _wipe()
    await _seed(admin_client, [
        _r("L1", "3", "05.04.2026", kunde="Mattes"),
        _r("L2", "-1", "06.04.2026", kunde="Brose"),
    ])
    r = await admin_client.get(
        "/api/procurement/otd/list?date_from=2026-04-01&date_to=2026-04-30"
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert {row["auftrag"] for row in rows} == {"L1", "L2"}


async def test_otd_read_requires_auth(client):
    r = await client.get("/api/procurement/otd")
    assert r.status_code in (401, 403)
