"""Sales KPI compute endpoints — contacts-weekly + orders-distribution.

v1.42: rep keys are the Wer token directly (e.g. "KARRER"), not a
Personio employee id.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models import (
    Interessent,
    Offer,
    SalesContact,
    SalesRecord,
    UploadBatch,
)

pytestmark = pytest.mark.asyncio


async def _wipe() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(SalesContact))
        await s.execute(delete(SalesRecord))
        await s.execute(delete(Interessent))
        await s.execute(delete(Offer))
        await s.execute(delete(UploadBatch))
        await s.commit()


async def test_contacts_weekly_one_rep_one_week(viewer_client):
    await _wipe()
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as s:
        s.add_all([
            SalesContact(
                contact_date=date(2026, 4, 27),
                employee_token="KARRER",
                contact_type="ERS",
                status=1,
                imported_at=now,
            ),
            SalesContact(
                contact_date=date(2026, 4, 28),
                employee_token="KARRER",
                contact_type="ORT",
                status=1,
                imported_at=now,
            ),
            # v1.52: ONL (online meeting) counts as a Besuch too.
            SalesContact(
                contact_date=date(2026, 4, 28),
                employee_token="KARRER",
                contact_type="ONL",
                status=1,
                imported_at=now,
            ),
            # v1.51: ANFR/EPA no longer count as interessenten — they're
            # sourced from the dedicated table now. This row should not
            # appear in any KPI bucket.
            SalesContact(
                contact_date=date(2026, 4, 29),
                employee_token="KARRER",
                contact_type="ANFR",
                status=1,
                imported_at=now,
            ),
            # v1.52: comment-prefix "Angebot" no longer drives the angebote
            # KPI — moved to a dedicated table sourced from AswKpf_ANG.
            SalesContact(
                contact_date=date(2026, 4, 30),
                employee_token="KARRER",
                contact_type="EMAIL",
                comment="Angebot 5000000",
                status=1,
                imported_at=now,
            ),
            # Status 0 row dropped
            SalesContact(
                contact_date=date(2026, 4, 27),
                employee_token="KARRER",
                contact_type="ERS",
                status=0,
                imported_at=now,
            ),
        ])
        # v1.51: 3 Interessenten with Datum Save in KW 18 / 2026.
        s.add_all([
            Interessent(adress_nr="1001", name="Acme A",
                        datum_save=date(2026, 4, 27), imported_at=now),
            Interessent(adress_nr="1002", name="Acme B",
                        datum_save=date(2026, 4, 30), imported_at=now),
            Interessent(adress_nr="1003", name="Acme C",
                        datum_save=date(2026, 5, 3), imported_at=now),
            # Outside the window — should not count.
            Interessent(adress_nr="1004", name="Acme D",
                        datum_save=date(2026, 5, 4), imported_at=now),
        ])
        # v1.52: two offers in KW 18 / 2026 by KARRER → angebote = 322611.16 + 84000 = 406611.16
        s.add_all([
            Offer(vorgang_nr="OFR-1", datum=date(2026, 4, 27),
                  erfasser="KARRER", wert_eur=Decimal("322611.16"),
                  imported_at=now),
            Offer(vorgang_nr="OFR-2", datum=date(2026, 5, 3),
                  erfasser="KARRER", wert_eur=Decimal("84000"),
                  imported_at=now),
            # Outside the window — should not count.
            Offer(vorgang_nr="OFR-3", datum=date(2026, 5, 4),
                  erfasser="KARRER", wert_eur=Decimal("999999"),
                  imported_at=now),
        ])
        await s.commit()

    r = await viewer_client.get(
        "/api/data/sales/contacts-weekly?from=2026-04-27&to=2026-05-03"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    week = next(w for w in body["weeks"] if w["iso_week"] == 18)
    bucket = week["per_employee"]["KARRER"]
    # interessenten is no longer in the per-employee bucket.
    # angebote is now an EUR sum from the dedicated offers table.
    assert bucket["erstkontakte"] == 1
    assert bucket["visits"] == 1  # only ORT counts here
    assert bucket["onl"] == 1     # ONL is its own field, stacked in the chart
    assert bucket["angebote"] == 406611.16
    # interessenten is a week-global total — 3 inside the window.
    assert week["interessenten"] == 3


async def test_contacts_weekly_multiple_reps(viewer_client):
    await _wipe()
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as s:
        s.add_all([
            SalesContact(
                contact_date=date(2026, 4, 27),
                employee_token="GUENDEL",
                contact_type="ERS",
                status=1,
                imported_at=now,
            ),
            SalesContact(
                contact_date=date(2026, 4, 28),
                employee_token="SCHMIDT",
                contact_type="ORT",
                status=1,
                imported_at=now,
            ),
        ])
        await s.commit()

    r = await viewer_client.get(
        "/api/data/sales/contacts-weekly?from=2026-04-27&to=2026-05-03"
    )
    assert r.status_code == 200
    week = r.json()["weeks"][0]
    assert "GUENDEL" in week["per_employee"]
    assert "SCHMIDT" in week["per_employee"]


async def test_orders_distribution_top3_share(viewer_client):
    await _wipe()
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as s:
        batch = UploadBatch(
            filename="t.csv",
            uploaded_at=now,
            row_count=5,
            error_count=0,
            status="success",
        )
        s.add(batch)
        await s.flush()
        for i, (cust, tot) in enumerate(
            [("A", 50), ("B", 30), ("C", 10), ("D", 5), ("E", 5)]
        ):
            s.add(
                SalesRecord(
                    upload_batch_id=batch.id,
                    order_number=f"O{i}",
                    order_date=date(2026, 4, 27),
                    customer_name=cust,
                    total_value=Decimal(tot),
                    # v1.44: rep is the ERP "Benutzer" column.
                    created_by_user="X",
                )
            )
        await s.commit()

    r = await viewer_client.get(
        "/api/data/sales/orders-distribution?from=2026-04-27&to=2026-04-30"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # 5 orders, totals 50+30+10+5+5 = 100. Top-3 = 50+30+10 = 90 → 90%.
    assert body["top3_share_pct"] == 90.0
    assert body["remaining_share_pct"] == 10.0
    names = [c["name"] for c in body["top3_customers"]]
    values = [c["total_value"] for c in body["top3_customers"]]
    assert names == ["A", "B", "C"]
    assert values == [50.0, 30.0, 10.0]
    # 5 attributed orders / 1 week / 1 rep → 5.0
    assert body["orders_per_week_per_rep"] == 5.0


async def test_orders_distribution_empty_range(viewer_client):
    await _wipe()
    r = await viewer_client.get(
        "/api/data/sales/orders-distribution?from=2026-04-27&to=2026-04-30"
    )
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "orders_per_week_per_rep": 0.0,
        "top3_share_pct": 0.0,
        "remaining_share_pct": 0.0,
        "top3_customers": [],
    }
