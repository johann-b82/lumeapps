"""Finanzperspektive / Materialkostenquote endpoints (v1.63).

These tests WIPE material_movements + material_prices and the MCQTEST* revenue
rows they seed — run only against a disposable test DB (acm_kpi_test), never
the live acm_kpi database. They isolate themselves in calendar year 2030 so
they never collide with real revenue data.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models import MaterialMovement, MaterialPrice, Revenue, UploadBatch

pytestmark = pytest.mark.asyncio


# ── file builders ────────────────────────────────────────────────────────

_WE_HEADER = [
    "Typ", "Vorgang Nr.", "Pos", "UPos", "Datum", "Artnr", "Bezeichnung 1",
    "Menge", "ME", "Preis", "Pos Wert",
]
_MOV_HEADER = [
    "Artikelnr", "Bezeichnung 1", "BuchDatum", "Bewegungsmenge", "BuchTyp",
    "Kommentar",
]


def _build(header: list[str], rows: list[dict]) -> bytes:
    lines = ["\t".join(header)]
    for r in rows:
        lines.append("\t".join(str(r.get(h, "")) for h in header))
    return ("\r\n".join(lines) + "\r\n").encode("cp1252")


def _we(vorgang, artnr, datum, menge, pos_wert, *, pos="1"):
    return {
        "Typ": "WE", "Vorgang Nr.": vorgang, "Pos": pos, "UPos": "0",
        "Datum": datum, "Artnr": artnr, "Bezeichnung 1": "x",
        "Menge": menge, "ME": "STK", "Preis": "0", "Pos Wert": pos_wert,
    }


def _mov(artnr, datum, menge, buchtyp):
    return {
        "Artikelnr": artnr, "Bezeichnung 1": "x", "BuchDatum": datum,
        "Bewegungsmenge": menge, "BuchTyp": buchtyp, "Kommentar": "c",
    }


async def _wipe() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(MaterialMovement))
        await s.execute(delete(MaterialPrice))
        await s.execute(
            delete(UploadBatch).where(
                UploadBatch.kind.in_(("material_movements", "material_prices"))
            )
        )
        await s.execute(delete(Revenue).where(Revenue.vorgang_nr.like("MCQTEST%")))
        await s.commit()


async def _seed_revenue(total_split: list[float]) -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as s:
        for i, wert in enumerate(total_split):
            s.add(
                Revenue(
                    vorgang_nr=f"MCQTEST-{i}",
                    typ="RG",
                    datum=date(2030, 4, 15),
                    customer_name="ACME",
                    wert_eur=wert,
                    imported_at=now,
                )
            )
        await s.commit()


async def _upload(admin_client, path, name, body):
    r = await admin_client.post(path, files={"file": (name, body, "text/plain")})
    assert r.status_code == 200, r.text
    return r.json()


async def _seed_all(admin_client):
    """L 0008: newest price 161,68/2000 = 0.08084 (older row at 1.0 must lose);
    L 3185: 6766,2/378 = 17.9. Consumption: L 0008 net 8, L 3185 5, H9999 100
    (unmatched), plus a K row that must be ignored."""
    we_body = _build(_WE_HEADER, [
        _we("V-OLD", "L 0008", "01.01.2029", "1000", "1000"),    # older → 1.0
        _we("V-NEW", "L 0008", "27.01.2030", "2000", "161,68"),  # newest → 0.08084
        _we("V-3185", "L 3185", "12.01.2030", "378", "6766,2"),  # 17.9
    ])
    await _upload(admin_client, "/api/upload-material-prices", "WE.txt", we_body)

    mov_body = _build(_MOV_HEADER, [
        _mov("L 0008", "10.04.2030", "-10", "M"),    # issue
        _mov("L 0008", "12.04.2030", "2", "SM"),     # reversal → net 8
        _mov("L 3185", "11.04.2030", "-5", "M"),     # 5
        _mov("H9999", "13.04.2030", "-100", "M"),    # unmatched (no WE price)
        _mov("L 0008", "14.04.2030", "-999", "K"),   # ignored (not M/SM)
    ])
    await _upload(
        admin_client, "/api/upload-material-movements", "LagBew.txt", mov_body
    )
    await _seed_revenue([600.0, 400.0])  # net Umsatz = 1000


# ── upload idempotency ─────────────────────────────────────────────────────


async def test_material_prices_reupload_updates_same_key(admin_client):
    await _wipe()
    b = _build(_WE_HEADER, [_we("V1", "L 1", "01.04.2030", "10", "50")])
    first = await _upload(admin_client, "/api/upload-material-prices", "WE.txt", b)
    assert first["rows_inserted"] == 1
    second = await _upload(admin_client, "/api/upload-material-prices", "WE.txt", b)
    assert second["rows_inserted"] == 0
    assert second["rows_updated"] == 1


async def test_material_movements_replace_by_date_range(admin_client):
    await _wipe()
    b = _build(_MOV_HEADER, [_mov("L 1", "10.04.2030", "-5", "M")])
    first = await _upload(
        admin_client, "/api/upload-material-movements", "M.txt", b
    )
    assert first["rows_inserted"] == 1
    assert first["date_range_from"] == "2030-04-10"
    # Re-upload the same single-day file: the existing row in [10.04,10.04] is
    # deleted, then re-inserted → idempotent (1 replaced, 1 inserted).
    second = await _upload(
        admin_client, "/api/upload-material-movements", "M.txt", b
    )
    assert second["rows_replaced"] == 1
    assert second["rows_inserted"] == 1


# ── Materialkostenquote KPI ────────────────────────────────────────────────


async def test_ratio_uses_net_consumption_newest_price_and_revenue(admin_client):
    await _wipe()
    await _seed_all(admin_client)
    r = await admin_client.get(
        "/api/finance/material-cost-ratio"
        "?date_from=2030-04-01&date_to=2030-04-30"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # L 0008: net 8 × 0.08084 = 0.64672 ; L 3185: 5 × 17.9 = 89.5
    assert abs(body["material_cost"] - 90.15) < 0.01
    assert body["revenue"] == 1000.0
    assert body["matched_articles"] == 2
    assert body["unmatched_articles"] == 1
    assert abs(body["ratio"] - (90.14672 / 1000.0)) < 1e-6


async def test_ratio_null_when_no_revenue(admin_client):
    await _wipe()
    await _seed_all(admin_client)
    r = await admin_client.get(
        "/api/finance/material-cost-ratio"
        "?date_from=2030-05-01&date_to=2030-05-31"
    )
    body = r.json()
    assert body["ratio"] is None
    assert body["revenue"] == 0.0


async def test_list_flags_unmatched_articles(admin_client):
    await _wipe()
    await _seed_all(admin_client)
    r = await admin_client.get(
        "/api/finance/material-cost-ratio/list"
        "?date_from=2030-04-01&date_to=2030-04-30"
    )
    assert r.status_code == 200, r.text
    rows = {row["artikelnr"]: row for row in r.json()}
    assert rows["H9999"]["has_price"] is False
    assert rows["H9999"]["material_cost"] is None
    assert rows["L 3185"]["has_price"] is True
    assert abs(rows["L 0008"]["consumed_qty"] - 8.0) < 1e-9


async def test_read_requires_auth(client):
    r = await client.get("/api/finance/material-cost-ratio")
    assert r.status_code in (401, 403)
