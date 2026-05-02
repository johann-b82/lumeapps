"""Sales KPI aggregation service (v1.44).

Two compute paths:

1. ``compute_contacts_weekly`` — group ``sales_contacts`` rows by
   (iso_year, iso_week, employee_token) and emit four counts per
   bucket: erstkontakte, interessenten, visits, angebote. Keyed by the
   ``Wer`` token from the Kontakte file directly.

2. ``compute_orders_distribution`` — three numbers for the combined
   "Auftragsverteilung" card:

   - **orders_per_week_per_rep** — mean orders per rep per week. Rep
     attribution is the ERP "Benutzer" column on each ``SalesRecord``
     (``created_by_user``); v1.44 dropped the v1.41/v1.42 Kontakte
     bridge.
   - **top3_share_pct** — sum(top-3 customers' total_value) /
     sum(all total_value), in percent. Always over the FULL set of
     orders in the date range, regardless of rep attribution.
   - **remaining_share_pct** — 100 − top3_share_pct.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SalesContact, SalesRecord


async def compute_contacts_weekly(
    session: AsyncSession, date_from: date, date_to: date,
) -> dict:
    """Return weekly KPI buckets keyed by Wer token."""
    rows = (
        await session.execute(
            select(SalesContact).where(
                and_(
                    SalesContact.status == 1,
                    SalesContact.contact_date >= date_from,
                    SalesContact.contact_date <= date_to,
                )
            )
        )
    ).scalars().all()

    agg: dict[tuple[int, int, str], dict[str, int]] = defaultdict(
        lambda: {"erstkontakte": 0, "interessenten": 0, "visits": 0, "angebote": 0}
    )
    for r in rows:
        token = r.employee_token
        if not token:
            continue
        iso_year, iso_week, _ = r.contact_date.isocalendar()
        bucket = agg[(iso_year, iso_week, token)]
        if r.contact_type == "ERS":
            bucket["erstkontakte"] += 1
        if r.contact_type in ("ANFR", "EPA"):
            bucket["interessenten"] += 1
        if r.contact_type == "ORT":
            bucket["visits"] += 1
        if (r.comment or "").strip().upper().startswith("ANGEBOT"):
            bucket["angebote"] += 1

    weeks: dict[tuple[int, int], dict] = {}
    for (yr, wk, token), bucket in agg.items():
        w = weeks.setdefault(
            (yr, wk),
            {
                "iso_year": yr,
                "iso_week": wk,
                "label": f"KW {wk:02d} / {yr}",
                "per_employee": {},
            },
        )
        w["per_employee"][token] = bucket

    sorted_weeks = sorted(weeks.values(), key=lambda w: (w["iso_year"], w["iso_week"]))
    return {"weeks": sorted_weeks}


async def compute_orders_distribution(
    session: AsyncSession, date_from: date, date_to: date,
) -> dict:
    """Orders/wk/rep + top-3 customer share + remaining share.

    ``orders_per_week_per_rep`` excludes €0 orders (consistent with the
    revenue cards above) and divides by the number of distinct sales
    reps that *created* any non-zero order in the range. v1.44: rep is
    taken from ``sales_records.created_by_user`` (ERP "Benutzer"
    column). When no rep can be resolved (e.g. legacy rows uploaded
    before v1.44) the metric is 0.0.
    """
    orders = (
        await session.execute(
            select(SalesRecord).where(
                and_(
                    SalesRecord.order_date.is_not(None),
                    SalesRecord.order_date >= date_from,
                    SalesRecord.order_date <= date_to,
                )
            )
        )
    ).scalars().all()

    if not orders:
        return {
            "orders_per_week_per_rep": 0.0,
            "top3_share_pct": 0.0,
            "remaining_share_pct": 0.0,
            "top3_customers": [],
        }

    # Exclude €0 (NULL counts as 0) orders from both the rate metric
    # and the customer-share metrics — matches the "Aufträge mit Wert
    # 0 € werden ausgeschlossen" disclaimer below the per_rep tile.
    nonzero = [o for o in orders if float(o.total_value or 0) > 0]

    creators = {
        (o.created_by_user or "").strip()
        for o in nonzero
        if (o.created_by_user or "").strip()
    }
    rep_count = len(creators)
    weeks = max(1, ((date_to - date_from).days // 7) + 1)
    if rep_count == 0:
        orders_per_week_per_rep = 0.0
    else:
        orders_per_week_per_rep = round(len(nonzero) / rep_count / weeks, 2)

    by_customer: dict[str, float] = defaultdict(float)
    for o in nonzero:
        by_customer[o.customer_name or ""] += float(o.total_value or 0)
    sorted_cust = sorted(by_customer.items(), key=lambda kv: kv[1], reverse=True)
    total = sum(by_customer.values()) or 1.0
    top3 = sorted_cust[:3]
    top3_sum = sum(v for _, v in top3)
    top3_pct = round(top3_sum / total * 100, 2)
    return {
        "orders_per_week_per_rep": orders_per_week_per_rep,
        "top3_share_pct": top3_pct,
        "remaining_share_pct": round(100.0 - top3_pct, 2),
        "top3_customers": [{"name": c, "total_value": round(v, 2)} for c, v in top3],
    }
