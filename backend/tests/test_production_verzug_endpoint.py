"""Produktion / "Aufträge in Verzug" endpoint (v1.76).

These tests WIPE auftrag_positionen + delivery_records — run only against a
disposable test DB (acm_kpi_test), never the live acm_kpi database.

Seeds AuftragPosition (target dates) + DeliveryRecord (actual dates) directly.
Verzug (Gesamtfertigstellung): per order, MAX(LS delivery_date) − MAX(AUF
lieferdatum); an order is in Verzug when that is > 0 days.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models import AuftragPosition, DeliveryRecord, UploadBatch
from app.services import production_kpi_aggregation

pytestmark = pytest.mark.asyncio


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
    positions: list[tuple[str, str, str]],
    deliveries: list[tuple[str, str]],
) -> None:
    """Insert AUF positions + LS delivery lines.

    ``positions``  — (order_nr, lieferdatum ISO, pos_typ_2) tuples.
    ``deliveries`` — (order_nr, delivery_date ISO) tuples.
    """
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as s:
        auf_batch = UploadBatch(
            filename="auf.txt", uploaded_at=now, row_count=len(positions),
            error_count=0, status="success", kind="auftrag_positionen",
        )
        ls_batch = UploadBatch(
            filename="ls.xlsx", uploaded_at=now, row_count=len(deliveries),
            error_count=0, status="success", kind="deliveries",
        )
        s.add_all([auf_batch, ls_batch])
        await s.flush()

        for i, (order_nr, ldate, ptyp2) in enumerate(positions):
            s.add(AuftragPosition(
                upload_batch_id=auf_batch.id,
                vorgang_nr=order_nr,
                pos=i,
                upos=0,
                lieferdatum=date.fromisoformat(ldate),
                pos_typ_2=ptyp2,
            ))
        for i, (order_nr, ddate) in enumerate(deliveries):
            s.add(DeliveryRecord(
                upload_batch_id=ls_batch.id,
                vorgang_nr=f"LS{i}",
                pos=i,
                upos=0,
                delivery_date=date.fromisoformat(ddate),
                order_nr=order_nr,
            ))
        await s.commit()


# A late(+5), B early(-1), C on-time(0), D open (no LS), E outside-window,
# F Seriengeschäft (AV-S) late(+10). April 2026 window.
async def _seed_all() -> None:
    await _seed(
        positions=[
            ("A", "2026-04-05", "AB"), ("A", "2026-04-10", "AB"),  # target 04-10
            ("B", "2026-04-18", "AB"), ("B", "2026-04-20", "AB"),  # target 04-20
            ("C", "2026-04-05", "AB"),                              # target 04-05
            ("D", "2026-04-10", "AB"),                              # open: no LS
            ("E", "2026-05-01", "AB"),                              # target May
            ("F", "2026-04-10", "AV-S"),                            # Serien
        ],
        deliveries=[
            ("A", "2026-04-08"), ("A", "2026-04-15"),  # actual 04-15 → +5
            ("B", "2026-04-19"),                         # actual 04-19 → −1
            ("C", "2026-04-05"),                         # 0
            ("E", "2026-05-10"),                         # actual May (outside)
            ("F", "2026-04-20"),                         # +10
        ],
    )


_APRIL = "date_from=2026-04-01&date_to=2026-04-30"


async def test_verzug_rate_is_in_verzug_over_total(admin_client):
    await _wipe()
    await _seed_all()
    r = await admin_client.get(f"/api/production/verzug?{_APRIL}")
    assert r.status_code == 200, r.text
    body = r.json()
    # A, B, C, F completed in April with a Zieltermin. D excluded (open, no
    # LS), E excluded (May completion).
    assert body["total_count"] == 4
    assert body["in_verzug_count"] == 2          # A (+5), F (+10)
    assert abs(body["rate"] - 0.5) < 1e-9
    assert abs(body["avg_delay"] - 3.5) < 1e-9   # (5 − 1 + 0 + 10) / 4


async def test_verzug_uses_latest_target_and_actual(admin_client):
    """Gesamtfertigstellung: MAX actual vs MAX target — an order is on time when
    its last delivery still beats its last Zieltermin."""
    await _wipe()
    await _seed(
        positions=[("M", "2026-04-05", "AB"), ("M", "2026-04-20", "AB")],  # tgt 04-20
        deliveries=[("M", "2026-04-10"), ("M", "2026-04-18")],             # act 04-18
    )
    body = (await admin_client.get(f"/api/production/verzug?{_APRIL}")).json()
    assert body["total_count"] == 1
    assert body["in_verzug_count"] == 0          # 04-18 ≤ 04-20 → on time


async def test_verzug_excludes_open_orders(admin_client):
    """An order with a Zieltermin but no Lieferschein yet is not counted."""
    await _wipe()
    await _seed(
        positions=[("OPEN", "2026-04-10", "AB")],
        deliveries=[],
    )
    body = (await admin_client.get(f"/api/production/verzug?{_APRIL}")).json()
    assert body["total_count"] == 0
    assert body["rate"] is None


async def test_verzug_window_filters_by_actual_completion(admin_client):
    await _wipe()
    await _seed_all()
    # May window catches only E (completed 2026-05-10).
    body = (await admin_client.get(
        "/api/production/verzug?date_from=2026-05-01&date_to=2026-05-31"
    )).json()
    assert body["total_count"] == 1
    assert body["in_verzug_count"] == 1          # 05-10 > 05-01 → +9


async def test_seriengeschaeft_filter_restricts_by_pos_typ_2(
    admin_client, monkeypatch
):
    """With the Pos-Typ-2 filter set, only orders with a matching position count."""
    await _wipe()
    await _seed_all()
    monkeypatch.setattr(
        production_kpi_aggregation,
        "SERIENGESCHAEFT_POS_TYP_2",
        frozenset({"AV-S"}),
    )
    body = (await admin_client.get(f"/api/production/verzug?{_APRIL}")).json()
    assert body["total_count"] == 1              # only F
    assert body["in_verzug_count"] == 1
    assert abs(body["rate"] - 1.0) < 1e-9


async def test_verzug_read_requires_auth(client):
    r = await client.get("/api/production/verzug")
    assert r.status_code in (401, 403)
