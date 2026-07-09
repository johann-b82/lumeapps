"""Produktion / "Aufträge in Verzug" endpoint (v1.76 / v1.78).

These tests WIPE auftrag_positionen + delivery_records — run only against a
disposable test DB (acm_kpi_test), never the live acm_kpi database.

v1.78 definition: windowed by Zieltermin (MAX AUF lieferdatum). An order counts
once decided (delivered, or Zieltermin past). In Verzug = delivered-late OR
open-&-overdue. Not-yet-due open orders are pending (excluded).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models import AuftragPosition, DeliveryRecord, UploadBatch
from app.services import production_kpi_aggregation

pytestmark = pytest.mark.asyncio

# A window firmly in the past (overdue for any realistic "today").
WFIRST = date(2024, 4, 1)
WLAST = date(2024, 4, 30)
_WINDOW = f"date_from={WFIRST.isoformat()}&date_to={WLAST.isoformat()}"


async def _wipe() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(DeliveryRecord))
        await s.execute(delete(AuftragPosition))
        await s.execute(
            delete(UploadBatch).where(
                UploadBatch.kind.in_(("deliveries", "auftrag_positionen"))
            )
        )
        await s.commit()


async def _seed(
    positions: list[tuple[str, date, str]],
    deliveries: list[tuple[str, date]],
) -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as s:
        auf_b = UploadBatch(filename="a.txt", uploaded_at=now, row_count=0,
                            error_count=0, status="success", kind="auftrag_positionen")
        ls_b = UploadBatch(filename="l.xlsx", uploaded_at=now, row_count=0,
                           error_count=0, status="success", kind="deliveries")
        s.add_all([auf_b, ls_b])
        await s.flush()
        for i, (order, tgt, ptyp2) in enumerate(positions):
            s.add(AuftragPosition(upload_batch_id=auf_b.id, vorgang_nr=order,
                                  pos=i, upos=0, lieferdatum=tgt, pos_typ_2=ptyp2))
        for i, (order, ddate) in enumerate(deliveries):
            s.add(DeliveryRecord(upload_batch_id=ls_b.id, vorgang_nr=f"LS{i}",
                                 pos=i, upos=0, delivery_date=ddate, order_nr=order))
        await s.commit()


# A late(+5), B on-time(-2), C overdue-open, plus out-of-window E.
async def _seed_window() -> None:
    await _seed(
        positions=[
            ("A", date(2024, 4, 10), "AB"),
            ("B", date(2024, 4, 20), "AB"),
            ("C", date(2024, 4, 5), "AB"),   # no LS -> overdue-open
            ("E", date(2024, 5, 10), "AB"),  # target in May -> out of window
        ],
        deliveries=[
            ("A", date(2024, 4, 15)),  # +5 late
            ("B", date(2024, 4, 18)),  # -2 on time
            ("E", date(2024, 5, 20)),  # late but out of window
        ],
    )


async def test_verzug_counts_delivered_late_and_overdue_open(admin_client):
    await _wipe()
    await _seed_window()
    body = (await admin_client.get(f"/api/production/verzug?{_WINDOW}")).json()
    # A (late), B (on-time), C (overdue-open) have their Zieltermin in April.
    assert body["total_count"] == 3
    assert body["in_verzug_count"] == 2          # A + C
    assert abs(body["rate"] - (2 / 3)) < 1e-9


async def test_verzug_excludes_not_yet_due_open_orders(admin_client):
    """An open order whose Zieltermin is still in the future is pending, not late."""
    await _wipe()
    future = date.today() + timedelta(days=400)
    await _seed(positions=[("FUT", future, "AB")], deliveries=[])
    body = (await admin_client.get(
        f"/api/production/verzug?date_from={future.replace(day=1).isoformat()}"
        f"&date_to={future.isoformat()}"
    )).json()
    assert body["total_count"] == 0
    assert body["rate"] is None


async def test_verzug_list_is_delivered_late_only(admin_client):
    await _wipe()
    await _seed_window()
    rows = (await admin_client.get(f"/api/production/verzug/list?{_WINDOW}")).json()
    assert [r["vorgang_nr"] for r in rows] == ["A"]
    assert rows[0]["verzug_tage"] == 5


async def test_overdue_list_is_open_and_overdue_only(admin_client):
    await _wipe()
    await _seed_window()
    rows = (await admin_client.get(f"/api/production/verzug/overdue?{_WINDOW}")).json()
    assert [r["vorgang_nr"] for r in rows] == ["C"]
    assert rows[0]["days_overdue"] == (date.today() - date(2024, 4, 5)).days


async def test_seriengeschaeft_filter_restricts_by_pos_typ_2(
    admin_client, monkeypatch
):
    await _wipe()
    await _seed(
        positions=[("A", date(2024, 4, 10), "AB"), ("S", date(2024, 4, 10), "AV-S")],
        deliveries=[("A", date(2024, 4, 15)), ("S", date(2024, 4, 20))],
    )
    monkeypatch.setattr(
        production_kpi_aggregation, "SERIENGESCHAEFT_POS_TYP_2", frozenset({"AV-S"})
    )
    body = (await admin_client.get(f"/api/production/verzug?{_WINDOW}")).json()
    assert body["total_count"] == 1      # only S
    assert body["in_verzug_count"] == 1


async def test_verzug_read_requires_auth(client):
    r = await client.get("/api/production/verzug")
    assert r.status_code in (401, 403)
