"""Customer-complaint rate aggregation (v1.58).

Formula
-------
    rate = Σ (8D complaint quantity)        within [first, last]
           ───────────────────────────────
           Σ (delivered quantity)            within [first, last]

* Numerator   — ``QualityRecord`` rows with ``art ∈ CUSTOMER_COMPLAINT_ART_CODES``,
                summed over either ``quantity`` (mode=``total``) or
                ``accepted_quantity`` (mode=``accepted``). Filter date is
                ``report_date``.
* Denominator — ``DeliveryRecord.quantity`` summed over rows whose
                ``delivery_date`` falls in the window.

Returns the rate as a fraction (e.g. ``0.0327`` = 3.27 %) so the frontend
keeps the locale-aware ``Intl.NumberFormat`` `style: "percent"` path that
already powers the HR / Sales KPI cards.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DeliveryRecord,
    GoodsReceiptRecord,
    QualityRecord,
)
from app.services.hr_kpi_aggregation import (
    prior_window_same_length,
    same_window_prior_year,
)


# Per-spec the goods-receipt denominator is scoped by "Klasse 1":
#   * Lieferanten-Quote (LIE RE)      → Klasse 1 = 'MAT' (Material)
#   * Unterauftragnehmer-Quote (UA RE) → Klasse 1 = 'FMD' (Fremdleistung)
# The AswKpf_WE export carries this distinction in the WGR (Warengruppe)
# column — physical material groups (STOFF, METALL, LEDER, A350, …)
# count as MAT; service/dienstleistung WGR codes count as FMD. Anything
# else is excluded from both. The two WGR sets live here so they can be
# extended without touching the aggregation body.
FMD_WGR_CODES: frozenset[str] = frozenset({"DIENST", "SERVIC"})

# When True (default) supplier denominator = all WE rows whose WGR is
# NOT in FMD_WGR_CODES (= the residual "material" partition). When the
# ERP later adds a fully tagged Klasse-1 export, swap this for an
# explicit MAT_WGR_CODES allowlist.
SUPPLIER_USES_FMD_COMPLEMENT: bool = True

# Both spellings observed in the ERP — see /api/quality/audit-findings
# diagnostic from earlier. We treat them as a single "Kundenreklamation"
# bucket so the dashboard rate isn't artificially halved.
CUSTOMER_COMPLAINT_ART_CODES: tuple[str, ...] = ("KUNRE", "KUN RE")

# Internal complaints — the spaced form 'INT RE' is the canonical code
# (10 reports in the live data). The packed form 'INRE' (45 reports)
# is also kept here because it shares the same semantic role, mirroring
# the KUNRE/KUN RE pairing. If 'INRE' turns out to be a different kind
# (e.g. Item-Not-Received), drop it from this tuple — no other code
# changes needed.
INTERNAL_COMPLAINT_ART_CODES: tuple[str, ...] = ("INT RE", "INRE")

# Supplier complaints — 25 + 183 reports in the live data.
SUPPLIER_COMPLAINT_ART_CODES: tuple[str, ...] = ("LIE RE", "LIERE")

# Subcontractor (Unterauftragnehmer) complaints — 15 reports under
# 'UA RE'. 'UARE' (packed) is not observed in the current data but kept
# as a safety net, same robustness pattern as the three pairs above.
SUBCONTRACTOR_COMPLAINT_ART_CODES: tuple[str, ...] = ("UA RE", "UARE")


ComplaintType = str  # "customer" | "internal" | "supplier" | "subcontractor"
QtyMode = str  # "total" | "accepted"


def _art_codes_for(complaint_type: ComplaintType) -> tuple[str, ...]:
    if complaint_type == "internal":
        return INTERNAL_COMPLAINT_ART_CODES
    if complaint_type == "supplier":
        return SUPPLIER_COMPLAINT_ART_CODES
    if complaint_type == "subcontractor":
        return SUBCONTRACTOR_COMPLAINT_ART_CODES
    # Default — customer complaints.
    return CUSTOMER_COMPLAINT_ART_CODES


def _complaint_qty_column(mode: QtyMode):
    """Return the QualityRecord column the numerator sum should use."""
    if mode == "accepted":
        return QualityRecord.accepted_quantity
    # Default "total" — the reklamierte Stück (Spalte K), regardless of
    # whether the customer later accepted the reclamation.
    return QualityRecord.quantity


async def _denominator_sum_for_window(
    db: AsyncSession,
    first: date,
    last: date,
    complaint_type: ComplaintType,
) -> float:
    """Compute the denominator (Bezugsmenge) for the active complaint type.

    * customer / internal — Σ DeliveryRecord.quantity over Lieferungen
      to customers (LS) in the window. Both downstream KPIs measure
      complaints AGAINST those outgoing deliveries, so the denominator
      stays unchanged from the v1.58 design.

    * supplier — Σ GoodsReceiptRecord.quantity where WGR is NOT in
      FMD_WGR_CODES (the Material residual; "Klasse 1 = MAT" per spec).
    * subcontractor — Σ GoodsReceiptRecord.quantity where WGR IS in
      FMD_WGR_CODES (Fremdleistung; "Klasse 1 = FMD").
    """
    if complaint_type in ("customer", "internal"):
        stmt = select(func.coalesce(func.sum(DeliveryRecord.quantity), 0)).where(
            DeliveryRecord.delivery_date >= first,
            DeliveryRecord.delivery_date <= last,
        )
        return float((await db.execute(stmt)).scalar_one() or 0)

    # supplier / subcontractor — Wareneingänge with WGR filter.
    stmt = select(func.coalesce(func.sum(GoodsReceiptRecord.quantity), 0)).where(
        GoodsReceiptRecord.receipt_date >= first,
        GoodsReceiptRecord.receipt_date <= last,
    )
    if complaint_type == "subcontractor":
        stmt = stmt.where(GoodsReceiptRecord.material_group.in_(FMD_WGR_CODES))
    elif complaint_type == "supplier":
        # Material = WE rows that are NOT Fremdleistung. Rows whose WGR
        # is NULL are also counted as material — the WGR column is only
        # mandatory on service positions in the ERP export.
        stmt = stmt.where(
            (GoodsReceiptRecord.material_group.notin_(FMD_WGR_CODES))
            | (GoodsReceiptRecord.material_group.is_(None))
        )
    return float((await db.execute(stmt)).scalar_one() or 0)


async def _sums_for_window(
    db: AsyncSession,
    first: date,
    last: date,
    qty_mode: QtyMode,
    complaint_type: ComplaintType,
) -> tuple[float, float]:
    """Return (complaint_qty_sum, denominator_qty_sum) — both NULL → 0.

    The numerator (complaints) always comes from QualityRecord; the
    denominator routes by complaint_type — see _denominator_sum_for_window.
    """
    complaint_col = _complaint_qty_column(qty_mode)
    art_codes = _art_codes_for(complaint_type)

    complaint_stmt = select(func.coalesce(func.sum(complaint_col), 0)).where(
        QualityRecord.report_date >= first,
        QualityRecord.report_date <= last,
        QualityRecord.art.in_(art_codes),
    )
    complaint_qty = float((await db.execute(complaint_stmt)).scalar_one() or 0)
    delivered_qty = await _denominator_sum_for_window(
        db, first, last, complaint_type
    )
    return complaint_qty, delivered_qty


def _rate(complaint: float, delivered: float) -> float | None:
    """rate = complaint / delivered. Undefined → None (avoids ∞)."""
    if delivered <= 0:
        return None
    return complaint / delivered


async def compute_complaint_rate(
    db: AsyncSession,
    first: date,
    last: date,
    qty_mode: QtyMode = "total",
    complaint_type: ComplaintType = "customer",
) -> dict:
    """Complaint rate for the window with prev/prev-year baselines.

    ``complaint_type`` selects which ``art`` codes go into the numerator
    sum: 'customer' uses KUNRE/KUN RE, 'internal' uses INT RE/INRE.
    """
    cur_c, cur_d = await _sums_for_window(db, first, last, qty_mode, complaint_type)

    prev_first, prev_last = prior_window_same_length(first, last)
    prev_c, prev_d = await _sums_for_window(
        db, prev_first, prev_last, qty_mode, complaint_type
    )

    ya_first, ya_last = same_window_prior_year(first, last)
    ya_c, ya_d = await _sums_for_window(
        db, ya_first, ya_last, qty_mode, complaint_type
    )

    return {
        "rate": _rate(cur_c, cur_d),
        "complaint_qty": cur_c,
        "delivered_qty": cur_d,
        "previous_period": _rate(prev_c, prev_d),
        "previous_year": _rate(ya_c, ya_d),
    }


async def compute_complaint_rate_history(
    db: AsyncSession,
    buckets: list[tuple[str, date, date]],
    qty_mode: QtyMode = "total",
    complaint_type: ComplaintType = "customer",
) -> list[dict]:
    """Per-bucket complaint rate; ``buckets`` from ``_bucket_windows``."""
    points: list[dict] = []
    for label, b_first, b_last in buckets:
        c, d = await _sums_for_window(db, b_first, b_last, qty_mode, complaint_type)
        points.append({
            "month": label,
            "rate": _rate(c, d),
            "complaint_qty": c,
            "delivered_qty": d,
        })
    return points


async def list_complaints(
    db: AsyncSession,
    first: date,
    last: date,
    complaint_type: ComplaintType = "customer",
    *,
    limit: int = 500,
) -> list[QualityRecord]:
    """Return QualityRecord rows for the verification table, filtered by type."""
    art_codes = _art_codes_for(complaint_type)
    stmt = (
        select(QualityRecord)
        .where(
            QualityRecord.report_date >= first,
            QualityRecord.report_date <= last,
            QualityRecord.art.in_(art_codes),
        )
        .order_by(QualityRecord.report_date.desc(), QualityRecord.report_nr.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


# Back-compat shim — old callers that pre-date the complaint_type param.
async def list_customer_complaints(
    db: AsyncSession,
    first: date,
    last: date,
    *,
    limit: int = 500,
) -> list[QualityRecord]:
    return await list_complaints(db, first, last, "customer", limit=limit)
