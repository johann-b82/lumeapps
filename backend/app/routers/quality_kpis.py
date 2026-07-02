"""Quality KPI endpoints (v1.49) — Audit-Findings Level 1 / Level 2.

Both endpoints accept an optional ``audit_types`` comma-separated list to
restrict the count to a subset of the four supported audit-type codes
(BH AUD, EX AUD, IN AUD, KU AUD). Omitting it counts all four.

Router-level viewer gate per CLAUDE.md §"Auth gate placement". Admin
write paths live in the uploads router.
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
)
from app.security.directus_auth import get_current_user
from app.services.complaint_rate_aggregation import (
    compute_complaint_rate,
    compute_complaint_rate_history,
    list_complaints,
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
