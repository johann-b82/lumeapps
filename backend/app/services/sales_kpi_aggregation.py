"""Sales KPI aggregation service (v1.44).

Two compute paths:

1. ``compute_contacts_weekly`` — emits per-week buckets for the
   Vertriebsaktivität card. Three of the KPIs are per-employee:

   - **erstkontakte**, **visits**, **angebote** — counts from
     ``sales_contacts`` rows (Typ ERS / ORT / comment-prefix "ANGEBOT"),
     grouped by the ``Wer`` token from the Kontakte file directly.

   The fourth KPI is global per week, NOT per rep:

   - **interessenten** — count from the dedicated ``interessenten``
     table (Adressen/Interessenten ERP export, keyed by Adress-Nr.,
     date = Datum Save). v1.51 retired the Kontakte
     ``Typ IN ('ANFR','EPA')`` heuristic when this dedicated source
     landed. The field therefore sits at week-level, not in
     ``per_employee``.

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

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Auftrag, Interessent, Offer, Revenue, SalesContact, SalesRecord  # noqa: F401


async def compute_contacts_weekly(
    session: AsyncSession, date_from: date, date_to: date,
) -> dict:
    """Return weekly KPI buckets.

    Three KPIs (erstkontakte, visits, angebote) come from ``sales_contacts``
    and are bucketed per (week, Wer-token). ``interessenten`` comes from
    the dedicated ``interessenten`` table and is a global per-week count
    — the source dump has no rep column.
    """
    contacts = (
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

    agg: dict[tuple[int, int, str], dict[str, float]] = defaultdict(
        lambda: {
            "erstkontakte": 0,
            "visits": 0,
            "onl": 0,
            "angebote": 0.0,
            # v1.56-b: weekly €-volume per rep from the auftraege table,
            # plotted as the 5th bar chart in the Vertriebsaktivität card.
            "orders_eur": 0.0,
        }
    )
    for r in contacts:
        token = r.employee_token
        if not token:
            continue
        iso_year, iso_week, _ = r.contact_date.isocalendar()
        bucket = agg[(iso_year, iso_week, token)]
        if r.contact_type == "ERS":
            bucket["erstkontakte"] += 1
        if r.contact_type == "ORT":
            bucket["visits"] += 1
        if r.contact_type == "ONL":
            bucket["onl"] += 1
        # v1.52: the comment-prefix heuristic for Angebote was retired;
        # offers now live in their own table and are summed in EUR below.

    weeks: dict[tuple[int, int], dict] = {}
    for (yr, wk, token), bucket in agg.items():
        w = weeks.setdefault(
            (yr, wk),
            {
                "iso_year": yr,
                "iso_week": wk,
                "label": f"KW {wk:02d} / {yr}",
                "interessenten": 0,
                "per_employee": {},
            },
        )
        w["per_employee"][token] = bucket

    # Interessenten — global per-week count from the dedicated table.
    int_rows = (
        await session.execute(
            select(
                func.extract("isoyear", Interessent.datum_save).label("iso_year"),
                func.extract("week", Interessent.datum_save).label("iso_week"),
                func.count().label("n"),
            )
            .where(
                and_(
                    Interessent.datum_save >= date_from,
                    Interessent.datum_save <= date_to,
                )
            )
            .group_by("iso_year", "iso_week")
        )
    ).all()
    for r in int_rows:
        key = (int(r.iso_year), int(r.iso_week))
        w = weeks.setdefault(
            key,
            {
                "iso_year": key[0],
                "iso_week": key[1],
                "label": f"KW {key[1]:02d} / {key[0]}",
                "interessenten": 0,
                "per_employee": {},
            },
        )
        w["interessenten"] = int(r.n)

    # Angebote — EUR sum per (iso-week, Erfasser) from the offers table.
    offer_rows = (
        await session.execute(
            select(
                func.extract("isoyear", Offer.datum).label("iso_year"),
                func.extract("week", Offer.datum).label("iso_week"),
                Offer.erfasser.label("erfasser"),
                func.sum(Offer.wert_eur).label("eur"),
            )
            .where(
                and_(
                    Offer.datum >= date_from,
                    Offer.datum <= date_to,
                )
            )
            .group_by("iso_year", "iso_week", Offer.erfasser)
        )
    ).all()
    for r in offer_rows:
        token = (r.erfasser or "").strip()
        if not token:
            continue
        key = (int(r.iso_year), int(r.iso_week))
        w = weeks.setdefault(
            key,
            {
                "iso_year": key[0],
                "iso_week": key[1],
                "label": f"KW {key[1]:02d} / {key[0]}",
                "interessenten": 0,
                "per_employee": {},
            },
        )
        bucket = w["per_employee"].setdefault(
            token,
            {
                "erstkontakte": 0,
                "visits": 0,
                "onl": 0,
                "angebote": 0.0,
                "orders_eur": 0.0,
            },
        )
        bucket["angebote"] = float(r.eur or 0)

    # v1.56-b: orders €-volume per (iso-week, erfasser) from the
    # auftraege table — 5th bar chart in the Vertriebsaktivität card.
    auftraege_rows = (
        await session.execute(
            select(
                func.extract("isoyear", Auftrag.datum).label("iso_year"),
                func.extract("week", Auftrag.datum).label("iso_week"),
                Auftrag.erfasser.label("erfasser"),
                func.sum(Auftrag.wert_eur).label("eur"),
            )
            .where(
                and_(
                    Auftrag.datum >= date_from,
                    Auftrag.datum <= date_to,
                )
            )
            .group_by("iso_year", "iso_week", Auftrag.erfasser)
        )
    ).all()
    for r in auftraege_rows:
        token = (r.erfasser or "").strip()
        if not token:
            continue
        key = (int(r.iso_year), int(r.iso_week))
        w = weeks.setdefault(
            key,
            {
                "iso_year": key[0],
                "iso_week": key[1],
                "label": f"KW {key[1]:02d} / {key[0]}",
                "interessenten": 0,
                "per_employee": {},
            },
        )
        bucket = w["per_employee"].setdefault(
            token,
            {
                "erstkontakte": 0,
                "visits": 0,
                "onl": 0,
                "angebote": 0.0,
                "orders_eur": 0.0,
            },
        )
        bucket["orders_eur"] = float(r.eur or 0)

    sorted_weeks = sorted(weeks.values(), key=lambda w: (w["iso_year"], w["iso_week"]))
    return {"weeks": sorted_weeks}


async def compute_orders_distribution(
    session: AsyncSession, date_from: date, date_to: date,
) -> dict:
    """€ / week / rep + top-3 customer share + remaining share.

    v1.54: re-sourced from the ``auftraege`` table (18-col
    ``AswKpf_AUF.txt`` export). Rep attribution uses ``Erfasst durch``
    (``Auftrag.erfasser``); customer grouping uses ``customer_name``.

    v1.54-b: ``orders_per_week_per_rep`` is now a €-volume metric
    (SUM(wert_eur) / rep_count / weeks), not an order count. The wire
    field name stays for backward compat — frontend renders it as
    currency in the card.

    €0 rows are excluded from both the rate metric and the customer
    share so storno / null-value rows can't distort the dashboard.
    """
    orders = (
        await session.execute(
            select(Auftrag).where(
                and_(
                    Auftrag.datum >= date_from,
                    Auftrag.datum <= date_to,
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

    nonzero = [o for o in orders if float(o.wert_eur or 0) > 0]

    creators = {
        (o.erfasser or "").strip()
        for o in nonzero
        if (o.erfasser or "").strip()
    }
    rep_count = len(creators)
    weeks = max(1, ((date_to - date_from).days // 7) + 1)
    if rep_count == 0:
        orders_per_week_per_rep = 0.0
    else:
        total_value = sum(float(o.wert_eur or 0) for o in nonzero)
        orders_per_week_per_rep = round(total_value / rep_count / weeks, 2)

    by_customer: dict[str, float] = defaultdict(float)
    for o in nonzero:
        by_customer[o.customer_name or ""] += float(o.wert_eur or 0)
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


async def compute_customer_share(
    session: AsyncSession,
    source: str,
    date_from: date,
    date_to: date,
    top_n: int = 14,
) -> dict:
    """Top-N customer share for the Kundenanteil waterfall card.

    Source switch:
      - ``"auftraege"`` → group ``auftraege.customer_name`` by SUM(wert_eur)
      - ``"revenues"``  → group ``revenues.customer_name`` by SUM(wert_eur),
        which includes GS (Gutschrift) rows with negative wert and is
        therefore net revenue.

    Returns:
        {
            "total_value": float,                    # denominator
            "top_share_pct": float,                  # top-N % of total
            "remaining_share_pct": float,            # 100 − top_share_pct
            "top_customers": [{"name": str,
                               "total_value": float,
                               "share_pct": float}, ...]
        }
    """
    if source not in {"auftraege", "revenues"}:
        raise ValueError(f"invalid source: {source!r}")

    model = Auftrag if source == "auftraege" else Revenue
    date_col = model.datum
    value_col = model.wert_eur

    # Single grouped query — let Postgres do the heavy lifting.
    stmt = (
        select(model.customer_name, func.sum(value_col).label("total_value"))
        .where(and_(date_col >= date_from, date_col <= date_to))
        .group_by(model.customer_name)
        .order_by(func.sum(value_col).desc())
    )
    rows = (await session.execute(stmt)).all()

    if not rows:
        return {
            "total_value": 0.0,
            "top_share_pct": 0.0,
            "remaining_share_pct": 0.0,
            "top_customers": [],
        }

    total = sum(float(r.total_value or 0) for r in rows)
    if total <= 0:
        return {
            "total_value": 0.0,
            "top_share_pct": 0.0,
            "remaining_share_pct": 0.0,
            "top_customers": [],
        }

    top = rows[:top_n]
    top_sum = sum(float(r.total_value or 0) for r in top)
    top_pct = round(top_sum / total * 100, 2)
    return {
        "total_value": round(total, 2),
        "top_share_pct": top_pct,
        "remaining_share_pct": round(100.0 - top_pct, 2),
        "top_customers": [
            {
                "name": r.customer_name or "",
                "total_value": round(float(r.total_value or 0), 2),
                "share_pct": round(float(r.total_value or 0) / total * 100, 2),
            }
            for r in top
        ],
    }
