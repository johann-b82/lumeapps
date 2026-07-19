"""Quality KPI endpoints (v1.49) — Audit-Findings Level 1 / Level 2.

Both endpoints accept an optional ``audit_types`` comma-separated list to
restrict the count to a subset of the four supported audit-type codes
(BH AUD, EX AUD, IN AUD, KU AUD). Omitting it counts all four.

Router-level viewer gate per CLAUDE.md §"Auth gate placement". Admin
write paths live in the uploads router, except for one v1.80 per-row
KPI opt-out toggle that lives here for locality:

    Admin-only: PATCH /api/quality/inspections/bookings/{id}

Compute-justified: clause 2 (server-side aggregation) — audit-findings,
complaint-rate, and inspections values/histories/lists are computed over the
quality tables and cannot be served as plain Directus collection reads.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.routers.hr_kpis import _bucket_windows, _validate_range
from app.schemas import (
    AuditFindingRow,
    AuditFindingsHistoryPoint,
    AuditFindingsValue,
    ComplaintRateHistoryPoint,
    ComplaintRateValue,
    CustomerComplaintRow,
    InspectionBookingRow,
    InspectionExcludeUpdate,
    InspectionListRow,
    InspectionsHistoryPoint,
    InspectionsValue,
)
from app.security.directus_auth import get_current_user, require_admin
from app.services.complaint_rate_aggregation import (
    compute_complaint_rate,
    compute_complaint_rate_history,
    list_complaints,
)
from app.services.inspection_aggregation import (
    compute_inspections,
    compute_inspections_history,
    list_inspection_bookings,
    list_inspections,
    set_booking_excluded,
)
from app.services.hr_kpi_aggregation import _month_bounds
from app.services.quality_kpi_aggregation import (
    AUDIT_ART_CODES,
    compute_audit_findings,
    compute_audit_findings_history,
    list_audit_findings,
)


router = APIRouter(
    prefix="/api/quality",
    tags=["quality-kpis"],
    dependencies=[Depends(get_current_user)],
)


def _parse_audit_types(raw: str | None) -> list[str] | None:
    """Comma-separated query string → validated list of audit-type codes.

    None / empty string → return None (caller treats as "all four").
    Unknown codes raise 400 so the frontend filter never silently drops
    selections.
    """
    if not raw:
        return None
    # Accept either "BH AUD,KU AUD" or "BH%20AUD,KU%20AUD" — URLSearchParams
    # url-encodes spaces; FastAPI Query unescapes them already.
    requested = [s.strip() for s in raw.split(",") if s.strip()]
    allowed = set(AUDIT_ART_CODES)
    invalid = [a for a in requested if a not in allowed]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown audit type(s): {invalid}. "
                f"Allowed: {sorted(allowed)}"
            ),
        )
    return requested or None


@router.get("/audit-findings", response_model=AuditFindingsValue)
async def get_audit_findings(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    audit_types: str | None = Query(
        None,
        description=(
            "Comma-separated list of audit-type codes to include "
            "(BH AUD, EX AUD, IN AUD, KU AUD). Omit to include all four."
        ),
    ),
    db: AsyncSession = Depends(get_async_db_session),
) -> AuditFindingsValue:
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)

    art_filter = _parse_audit_types(audit_types)
    payload = await compute_audit_findings(db, date_from, date_to, art_filter)
    return AuditFindingsValue(**payload)


@router.get(
    "/audit-findings/list",
    response_model=list[AuditFindingRow],
)
async def get_audit_findings_list(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    audit_types: str | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[AuditFindingRow]:
    """Findings list for the verification table under the charts."""
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)

    art_filter = _parse_audit_types(audit_types)
    rows = await list_audit_findings(db, date_from, date_to, art_filter)
    return [AuditFindingRow.model_validate(r) for r in rows]


@router.get(
    "/audit-findings/history",
    response_model=list[AuditFindingsHistoryPoint],
)
async def get_audit_findings_history(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    audit_types: str | None = Query(None),
    granularity: str | None = Query(
        None,
        description=(
            "Override the auto-picked bucket granularity. "
            "Allowed: weekly, monthly, quarterly, yearly. "
            "Omit for auto (length-based)."
        ),
    ),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[AuditFindingsHistoryPoint]:
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)

    art_filter = _parse_audit_types(audit_types)
    buckets = _bucket_windows(date_from, date_to, granularity)
    points = await compute_audit_findings_history(db, buckets, art_filter)
    return [AuditFindingsHistoryPoint(**p) for p in points]


# ── v1.58 — Complaints (rate + list, customer or internal) ─────────────


_ALLOWED_QTY_MODES = {"total", "accepted"}
_ALLOWED_COMPLAINT_TYPES = {"customer", "internal", "supplier", "subcontractor"}


def _validate_qty_mode(mode: str) -> str:
    if mode not in _ALLOWED_QTY_MODES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown qty_mode={mode!r}. "
                f"Allowed: {sorted(_ALLOWED_QTY_MODES)}"
            ),
        )
    return mode


def _validate_complaint_type(value: str) -> str:
    if value not in _ALLOWED_COMPLAINT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown complaint_type={value!r}. "
                f"Allowed: {sorted(_ALLOWED_COMPLAINT_TYPES)}"
            ),
        )
    return value


@router.get("/complaint-rate", response_model=ComplaintRateValue)
async def get_complaint_rate(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    qty_mode: str = Query(
        "total",
        description=(
            "Numerator quantity column: 'total' = Spalte K Menge (default), "
            "'accepted' = Spalte L akzeptierte Menge."
        ),
    ),
    complaint_type: str = Query(
        "customer",
        description=(
            "Which art codes feed the numerator: 'customer' = KUNRE/KUN RE, "
            "'internal' = INT RE/INRE."
        ),
    ),
    db: AsyncSession = Depends(get_async_db_session),
) -> ComplaintRateValue:
    _validate_range(date_from, date_to)
    _validate_qty_mode(qty_mode)
    _validate_complaint_type(complaint_type)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    payload = await compute_complaint_rate(
        db, date_from, date_to, qty_mode, complaint_type
    )
    return ComplaintRateValue(**payload)


@router.get(
    "/complaint-rate/history",
    response_model=list[ComplaintRateHistoryPoint],
)
async def get_complaint_rate_history(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    qty_mode: str = Query("total"),
    complaint_type: str = Query("customer"),
    granularity: str | None = Query(
        None,
        description=(
            "Override the auto-picked bucket granularity. "
            "Allowed: weekly, monthly, quarterly, yearly. "
            "Omit for auto (length-based)."
        ),
    ),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[ComplaintRateHistoryPoint]:
    _validate_range(date_from, date_to)
    _validate_qty_mode(qty_mode)
    _validate_complaint_type(complaint_type)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    buckets = _bucket_windows(date_from, date_to, granularity)
    points = await compute_complaint_rate_history(
        db, buckets, qty_mode, complaint_type
    )
    return [ComplaintRateHistoryPoint(**p) for p in points]


@router.get(
    "/complaints/list",
    response_model=list[CustomerComplaintRow],
)
async def get_complaints_list(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    complaint_type: str = Query("customer"),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[CustomerComplaintRow]:
    """Complaint rows for the verification table on the Reklamationen view."""
    _validate_range(date_from, date_to)
    _validate_complaint_type(complaint_type)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    rows = await list_complaints(db, date_from, date_to, complaint_type)
    return [CustomerComplaintRow.model_validate(r) for r in rows]


# ── v1.70 — Inspections (Qualitätsprüfungen: große + kleine Produkte) ──


@router.get("/inspections", response_model=InspectionsValue)
async def get_inspections(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> InspectionsValue:
    """Anzahl geprüfter Produkte per size tier (large / small).

    STUB — the aggregation returns 0 counts until the input pipeline
    is specified. Delta baselines mirror /audit-findings.
    """
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    payload = await compute_inspections(db, date_from, date_to)
    return InspectionsValue(**payload)


@router.get(
    "/inspections/history",
    response_model=list[InspectionsHistoryPoint],
)
async def get_inspections_history(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    granularity: str | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[InspectionsHistoryPoint]:
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    buckets = _bucket_windows(date_from, date_to, granularity)
    points = await compute_inspections_history(db, buckets)
    return [InspectionsHistoryPoint(**p) for p in points]


@router.get(
    "/inspections/list",
    response_model=list[InspectionListRow],
)
async def get_inspections_list(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[InspectionListRow]:
    """Verification table for the Qualitätsprüfung view.

    One row per (Bezeichnung, size_class) with count/qty aggregates so
    the user can scan how each product was classified and how often it
    was booked in the window.
    """
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    rows = await list_inspections(db, date_from, date_to)
    return [InspectionListRow(**r) for r in rows]


@router.get(
    "/inspections/bookings",
    response_model=list[InspectionBookingRow],
)
async def get_inspection_bookings(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[InspectionBookingRow]:
    """Raw AswQs2151 bookings in the window (v1.80).

    Returns every row (excluded=true too) so the frontend can render the
    per-row checkbox in its correct state. Ordered newest first.
    """
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    rows = await list_inspection_bookings(db, date_from, date_to)
    return [InspectionBookingRow(**r) for r in rows]


@router.patch(
    "/inspections/bookings/{booking_id}",
    response_model=InspectionBookingRow,
    dependencies=[Depends(require_admin)],
)
async def patch_inspection_booking(
    booking_id: int,
    payload: InspectionExcludeUpdate,
    db: AsyncSession = Depends(get_async_db_session),
) -> InspectionBookingRow:
    """Toggle a booking's KPI opt-out flag (admin-only, v1.80)."""
    updated = await set_booking_excluded(db, booking_id, payload.excluded)
    if updated is None:
        raise HTTPException(status_code=404, detail="booking not found")
    return InspectionBookingRow(**updated)
