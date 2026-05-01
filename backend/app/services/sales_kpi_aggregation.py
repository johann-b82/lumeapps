"""Sales KPI aggregation service (v1.41).

Two compute paths:

1. ``compute_contacts_weekly`` — group ``sales_contacts`` rows by
   (iso_year, iso_week, personio_employee_id) and emit four counts per
   bucket: erstkontakte, interessenten, visits, angebote. Rows with an
   unmapped ``employee_token`` (no row in ``sales_employee_aliases``)
   are silently dropped.

2. ``compute_orders_distribution`` — three numbers for the combined
   "Auftragsverteilung" card:

   - **orders_per_week_per_rep** — mean orders per rep per week. Rep
     attribution is bridged through the Kontakte file: a SalesRecord is
     attributed to the rep recorded on a Kontakte row whose ``comment``
     starts with ``Angebot <order_number>``. Orders without a matching
     Kontakte row are dropped from the rep-mean (still counted for the
     customer-share metrics below).
   - **top3_share_pct** — sum(top-3 customers' total_value) /
     sum(all total_value), in percent. Always over the FULL set of
     orders in the date range, regardless of rep attribution.
   - **remaining_share_pct** — 100 − top3_share_pct.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PersonioEmployee,
    SalesContact,
    SalesEmployeeAlias,
    SalesRecord,
)

_ANGEBOT_RE = re.compile(r"^\s*Angebot\s+(\S+)", re.IGNORECASE)


async def compute_contacts_weekly(
    session: AsyncSession, date_from: date, date_to: date,
) -> dict:
    """Return weekly KPI buckets per Personio sales rep."""
    aliases = (
        await session.execute(
            select(
                SalesEmployeeAlias.employee_token,
                SalesEmployeeAlias.personio_employee_id,
            )
        )
    ).all()
    token_to_emp: dict[str, int] = {row[0]: row[1] for row in aliases}
    if not token_to_emp:
        return {"weeks": [], "employees": {}}

    rows = (
        await session.execute(
            select(SalesContact).where(
                and_(
                    SalesContact.status == 1,
                    SalesContact.contact_date >= date_from,
                    SalesContact.contact_date <= date_to,
                    SalesContact.employee_token.in_(list(token_to_emp.keys())),
                )
            )
        )
    ).scalars().all()

    agg: dict[tuple[int, int, int], dict[str, int]] = defaultdict(
        lambda: {"erstkontakte": 0, "interessenten": 0, "visits": 0, "angebote": 0}
    )
    for r in rows:
        emp_id = token_to_emp.get(r.employee_token)
        if emp_id is None:  # defensive — shouldn't happen given the in_() filter
            continue
        iso_year, iso_week, _ = r.contact_date.isocalendar()
        bucket = agg[(iso_year, iso_week, emp_id)]
        if r.contact_type == "ERS":
            bucket["erstkontakte"] += 1
        if r.contact_type in ("ANFR", "EPA"):
            bucket["interessenten"] += 1
        if r.contact_type == "ORT":
            bucket["visits"] += 1
        if (r.comment or "").strip().upper().startswith("ANGEBOT"):
            bucket["angebote"] += 1

    weeks: dict[tuple[int, int], dict] = {}
    for (yr, wk, emp_id), bucket in agg.items():
        w = weeks.setdefault(
            (yr, wk),
            {
                "iso_year": yr,
                "iso_week": wk,
                "label": f"KW {wk:02d} / {yr}",
                "per_employee": {},
            },
        )
        w["per_employee"][emp_id] = bucket

    employees = {
        e.id: f"{e.first_name or ''} {e.last_name or ''}".strip() or f"#{e.id}"
        for e in (
            await session.execute(
                select(PersonioEmployee).where(
                    PersonioEmployee.id.in_(list(token_to_emp.values()))
                )
            )
        ).scalars().all()
    }
    sorted_weeks = sorted(weeks.values(), key=lambda w: (w["iso_year"], w["iso_week"]))
    return {"weeks": sorted_weeks, "employees": employees}


async def _build_order_to_rep_bridge(
    session: AsyncSession, date_from: date, date_to: date,
) -> dict[str, int]:
    """Map ``order_number`` → personio_employee_id via Kontakte comments.

    A Kontakte row whose ``comment`` starts with ``Angebot <number>``
    associates that order_number with the rep recorded in ``Wer``.
    Multiple Kontakte rows can mention the same order_number; we take
    the most recent contact_date as authoritative.
    """
    aliases = (
        await session.execute(
            select(
                SalesEmployeeAlias.employee_token,
                SalesEmployeeAlias.personio_employee_id,
            )
        )
    ).all()
    token_to_emp: dict[str, int] = {row[0]: row[1] for row in aliases}
    if not token_to_emp:
        return {}

    # Look back further than the date range — a quote can predate the order.
    contact_lookback = date_from.replace(year=date_from.year - 5)
    rows = (
        await session.execute(
            select(SalesContact).where(
                and_(
                    SalesContact.contact_date >= contact_lookback,
                    SalesContact.contact_date <= date_to,
                    SalesContact.employee_token.in_(list(token_to_emp.keys())),
                )
            )
        )
    ).scalars().all()

    latest: dict[str, tuple[date, int]] = {}
    for r in rows:
        m = _ANGEBOT_RE.match(r.comment or "")
        if not m:
            continue
        order_no = m.group(1)
        emp_id = token_to_emp.get(r.employee_token)
        if emp_id is None:
            continue
        existing = latest.get(order_no)
        if existing is None or r.contact_date > existing[0]:
            latest[order_no] = (r.contact_date, emp_id)
    return {ord_no: emp_id for ord_no, (_, emp_id) in latest.items()}


async def compute_orders_distribution(
    session: AsyncSession, date_from: date, date_to: date,
) -> dict:
    """Orders/wk/rep + top-3 customer share + remaining share."""
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

    bridge = await _build_order_to_rep_bridge(session, date_from, date_to)

    # Orders attributed to a rep
    attributed = [o for o in orders if o.order_number in bridge]
    rep_ids = {bridge[o.order_number] for o in attributed}
    weeks = max(1, ((date_to - date_from).days // 7) + 1)
    rep_count = max(1, len(rep_ids))
    orders_per_week_per_rep = (
        round(len(attributed) / weeks / rep_count, 2) if rep_count else 0.0
    )

    # Customer concentration over the FULL order set
    by_customer: dict[str, float] = defaultdict(float)
    for o in orders:
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
        "top3_customers": [c for c, _ in top3],
    }
