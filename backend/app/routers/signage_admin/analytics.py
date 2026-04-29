"""Phase 53 SGN-ANA-01 — Analytics-lite devices endpoint.

GET /api/signage/analytics/devices
  → list[DeviceAnalyticsRead]

Computes per non-revoked device:
  - uptime_24h_pct: % of distinct minute-buckets with ≥1 heartbeat in the last 24 h
  - missed_windows_24h: denominator - buckets_with_heartbeat
  - window_minutes: min(1440, minutes since device's oldest retained heartbeat)

Partial-history denominator (D-06) keeps fresh devices honest — a Pi
provisioned 30 min ago shows 100 % over a 30-min window rather than a
misleading 100 % over 24 h.

Admin gate inherited from the parent signage_admin router (do NOT add a
local ``dependencies=`` kwarg — that would double-apply and is a style
violation per signage_admin/__init__.py module docstring).

Compute-justified: clause 3 (multi-row aggregation compute).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.schemas.signage import DeviceAnalyticsRead

router = APIRouter(prefix="/analytics/devices", tags=["signage-admin-analytics"])

# Bucketed uptime query — see .planning/phases/53-analytics-lite/53-RESEARCH.md
# Pattern 1. Composite PK (device_id, ts) on signage_heartbeat_event makes
# the WHERE ts >= cutoff + GROUP BY device_id a single PK range scan.
_ANALYTICS_SQL = """
    WITH window_bounds AS (
        SELECT now() - interval '24 hours' AS cutoff_start,
               now()                         AS cutoff_end
    ),
    per_device AS (
        SELECT
            he.device_id,
            COUNT(DISTINCT date_trunc('minute', he.ts)) AS buckets_with_hb,
            EXTRACT(EPOCH FROM (now() - MIN(he.ts))) / 60.0 AS first_hb_age_min
        FROM signage_heartbeat_event he, window_bounds wb
        WHERE he.ts >= wb.cutoff_start
          AND he.ts <  wb.cutoff_end
        GROUP BY he.device_id
    )
    SELECT
        d.id AS device_id,
        LEAST(1440, COALESCE(CEIL(p.first_hb_age_min)::int, 0)) AS denominator,
        COALESCE(p.buckets_with_hb, 0)::int AS buckets_with_hb
    FROM signage_devices d
    LEFT JOIN per_device p ON p.device_id = d.id
    WHERE d.revoked_at IS NULL
    ORDER BY d.id
"""


@router.get("", response_model=list[DeviceAnalyticsRead])
async def list_device_analytics(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[DeviceAnalyticsRead]:
    rows = (await db.execute(text(_ANALYTICS_SQL))).mappings().all()
    out: list[DeviceAnalyticsRead] = []
    for r in rows:
        denom = int(r["denominator"])
        buckets = int(r["buckets_with_hb"])
        if denom == 0:
            out.append(
                DeviceAnalyticsRead(
                    device_id=r["device_id"],
                    uptime_24h_pct=None,
                    missed_windows_24h=0,
                    window_minutes=0,
                )
            )
            continue
        pct = round((buckets / denom) * 100, 1)
        missed = max(denom - buckets, 0)
        out.append(
            DeviceAnalyticsRead(
                device_id=r["device_id"],
                uptime_24h_pct=pct,
                missed_windows_24h=missed,
                window_minutes=denom,
            )
        )
    return out
