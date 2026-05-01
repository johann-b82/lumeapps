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
    SalesContact,
    SalesRecord,
    UploadBatch,
)

pytestmark = pytest.mark.asyncio


async def _wipe() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(SalesContact))
        await s.execute(delete(SalesRecord))
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
            SalesContact(
                contact_date=date(2026, 4, 29),
                employee_token="KARRER",
                contact_type="ANFR",
                status=1,
                imported_at=now,
            ),
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
        await s.commit()

    r = await viewer_client.get(
        "/api/data/sales/contacts-weekly?from=2026-04-27&to=2026-05-03"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    week = next(w for w in body["weeks"] if w["iso_week"] == 18)
    bucket = week["per_employee"]["KARRER"]
    assert bucket == {
        "erstkontakte": 1,
        "interessenten": 1,
        "visits": 1,
        "angebote": 1,
    }


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
                )
            )
        # Bridge: a Kontakte row attributing each order to rep "X".
        for i in range(5):
            s.add(
                SalesContact(
                    contact_date=date(2026, 4, 1),
                    employee_token="X",
                    contact_type="EMAIL",
                    comment=f"Angebot O{i}",
                    status=1,
                    imported_at=now,
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
    assert sorted(body["top3_customers"]) == ["A", "B", "C"]
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
