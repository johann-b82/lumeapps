"""/api/signage/pair/* — device pairing flow (SGN-BE-03).

Three endpoints:
  POST /api/signage/pair/request   -> public, rate-limited (D-09)
  GET  /api/signage/pair/status    -> public, polled by kiosk
  POST /api/signage/pair/claim     -> admin-only (per-endpoint gate)

INTENTIONAL EXCEPTION to cross-cutting hazard #5 ("router-level admin gate via
APIRouter(dependencies=[...])"): `/request` and `/status` are deliberately
*public* — an un-paired kiosk has no token to present. `/claim` is
admin-gated per-endpoint instead of router-level. Phase 43's dep-audit test
(SGN-BE-09) must permit this exception; do NOT "fix" by moving the admin gate
to the APIRouter constructor.

Design notes:
  - Pairing code generation: pure-function helper in app.services.signage_pairing
    plus a CODE_GEN_RETRIES loop in POST /request. The partial-unique index
    `uix_signage_pairing_sessions_code_active` (Phase 41) is the primary guard;
    retries are defense-in-depth against the astronomically unlikely collision
    between unclaimed sessions.
  - Atomic claim: single `UPDATE ... WHERE claimed_at IS NULL AND expires_at > now()
    RETURNING id` (PITFALLS §13 / D-06). No SELECT-then-UPDATE; that races.
    Expiration predicate sits in the WHERE clause because the partial-unique
    index does NOT cover `expires_at` (SGN-DB-02 amendment — `now()` is not
    IMMUTABLE and Postgres rejects it from partial-index predicates).
  - Delete-on-deliver (D-08 / RESEARCH Pitfall 2): on the first successful
    GET /status after claim, we mint the JWT AND delete the pairing-session
    row inside the same transaction. Second poll returns `expired`. This is the
    exactly-once delivery semantic that keeps the device token from being
    re-fetchable by anyone who snoops the pairing_session_id.
  - We do NOT write to the devices-table hash column under the JWT format
    (RESEARCH anti-pattern — that column is only for an opaque-token variant
    we deliberately did not pick).

Compute-justified: clause 2 (pairing-token Fernet encrypt).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.database import get_async_db_session
from app.models import SignageDevice, SignageDeviceTagMap, SignagePairingSession
from app.schemas.signage import (
    SignagePairingClaimRequest,
    SignagePairingRequestResponse,
    SignagePairingStatusResponse,
)
from app.security.directus_auth import get_current_user, require_admin
from app.security.rate_limit import rate_limit_pair_request
from app.services.signage_pairing import (
    format_for_display,
    generate_pairing_code,
    mint_device_jwt,
)

# See module docstring: intentional exception to the router-level admin-gate
# rule. /request and /status are public; /claim is admin-gated per-endpoint.
router = APIRouter(prefix="/api/signage/pair", tags=["signage-pair"])

PAIRING_TTL_SECONDS = 600  # 10 minutes — ROADMAP SC #1
CODE_GEN_RETRIES = 5       # defense in depth; the partial-unique index is primary


# ---------------------------------------------------------------------------
# POST /request — public, rate-limited
# ---------------------------------------------------------------------------


@router.post(
    "/request",
    response_model=SignagePairingRequestResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_pair_request)],
)
async def request_pairing_code(
    db: AsyncSession = Depends(get_async_db_session),
) -> SignagePairingRequestResponse:
    """Generate a fresh 10-minute pairing session and return the display code."""
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=PAIRING_TTL_SECONDS)
    last_exc: IntegrityError | None = None
    for _ in range(CODE_GEN_RETRIES):
        code = generate_pairing_code()
        row = SignagePairingSession(code=code, expires_at=expires_at)
        db.add(row)
        try:
            await db.commit()
        except IntegrityError as exc:
            # Collision on the partial-unique index — retry with a fresh code.
            await db.rollback()
            last_exc = exc
            continue
        await db.refresh(row)
        return SignagePairingRequestResponse(
            pairing_code=format_for_display(row.code),
            pairing_session_id=row.id,
            expires_in=PAIRING_TTL_SECONDS,
        )

    # Exceeded CODE_GEN_RETRIES — system is saturated; shed load.
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="pairing system saturated, retry shortly",
        headers={"Retry-After": "60"},
    ) from last_exc


# ---------------------------------------------------------------------------
# GET /status — public, delete-on-deliver
# ---------------------------------------------------------------------------


@router.get("/status", response_model=SignagePairingStatusResponse)
async def get_pairing_status(
    pairing_session_id: str,
    db: AsyncSession = Depends(get_async_db_session),
) -> SignagePairingStatusResponse:
    """Poll pairing status; on the FIRST poll after claim, deliver the JWT
    and delete the pairing-session row (exactly-once semantic per D-08)."""
    # Parse UUID defensively; unknown/unparseable IDs degrade to `expired`
    # (not 404) per RESEARCH §"Open Questions" Q1 — avoids leaking a
    # timing oracle for "did this id ever exist".
    from uuid import UUID

    try:
        session_id = UUID(pairing_session_id)
    except (TypeError, ValueError):
        return SignagePairingStatusResponse(status="expired", device_token=None)

    row = (
        await db.execute(
            select(SignagePairingSession).where(
                SignagePairingSession.id == session_id
            )
        )
    ).scalar_one_or_none()

    # 1. Unknown id
    if row is None:
        return SignagePairingStatusResponse(status="expired", device_token=None)

    now = datetime.now(timezone.utc)

    # 2. Pending & still in TTL window
    if row.claimed_at is None and row.expires_at > now:
        return SignagePairingStatusResponse(status="pending", device_token=None)

    # 3. Pending but TTL elapsed — cron will sweep; present as expired
    if row.claimed_at is None and row.expires_at <= now:
        return SignagePairingStatusResponse(status="expired", device_token=None)

    # 4. Claimed — mint JWT AND delete row in the same transaction.
    #    The delete-on-deliver invariant (D-08 / RESEARCH Pitfall 2) keeps the
    #    device token from being re-fetchable on subsequent polls.
    assert row.claimed_at is not None and row.device_id is not None
    token = mint_device_jwt(row.device_id)
    await db.execute(
        delete(SignagePairingSession).where(SignagePairingSession.id == row.id)
    )
    await db.commit()
    return SignagePairingStatusResponse(status="claimed", device_token=token)


# ---------------------------------------------------------------------------
# POST /claim — admin-gated, atomic claim pattern
# ---------------------------------------------------------------------------


@router.post(
    "/claim",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)
async def claim_pairing_code(
    payload: SignagePairingClaimRequest,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Bind a pending pairing code to a newly-created device, atomically."""
    # Accept both dashed ("ABC-123") and undashed ("ABC123") forms.
    raw_code = payload.code.replace("-", "").upper()

    # Insert the device row first; flush (not commit) to populate device.id.
    device = SignageDevice(name=payload.device_name, status="pending")
    db.add(device)
    await db.flush()

    # Atomic claim: single UPDATE gates on `claimed_at IS NULL` AND
    # `expires_at > now()`. PITFALLS §13 — SELECT-then-UPDATE would race.
    # The partial-unique index does NOT enforce the expiry half of the predicate
    # (SGN-DB-02 amendment: now() is STABLE, not IMMUTABLE), so we MUST carry
    # the expires_at check in the WHERE clause.
    result = await db.execute(
        update(SignagePairingSession)
        .where(
            SignagePairingSession.code == raw_code,
            SignagePairingSession.claimed_at.is_(None),
            SignagePairingSession.expires_at > func.now(),
        )
        .values(claimed_at=func.now(), device_id=device.id)
        .returning(SignagePairingSession.id)
    )
    claimed = result.scalar_one_or_none()
    if claimed is None:
        # No matching pending row — rollback discards the inserted device so we
        # do not leak a half-bound row into the devices table.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="pairing code invalid, expired, or already claimed",
        )

    # Tag linkage — optional. Bulk insert into the device-tag-map join table.
    if payload.tag_ids:
        await db.execute(
            insert(SignageDeviceTagMap),
            [
                {"device_id": device.id, "tag_id": tag_id}
                for tag_id in payload.tag_ids
            ],
        )

    await db.commit()
    # 204 — no response body


# ---------------------------------------------------------------------------
# POST /devices/{device_id}/revoke — admin-only device revocation (D-14)
# ---------------------------------------------------------------------------
#
# Minimal revoke endpoint to satisfy ROADMAP SC #5 inside Phase 42. Phase 43
# may consolidate device admin CRUD under /api/signage/devices/{id}; until
# that router lands, the revoke operation lives on the pair router so
# Phase 42 can be verified end-to-end.
#
# SGN-DB-02 / D-13 note: we never write to signage_devices.device_token_hash —
# that column is reserved for an opaque-token variant we deliberately did
# not pick. The scoped-JWT scheme carries revocation state via revoked_at
# alone; get_current_device (Plan 42-01) re-reads this column on every
# request, so the 401 on subsequent calls is automatic.


@router.post(
    "/devices/{device_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)
async def revoke_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Flip ``signage_devices.revoked_at = now()`` for the given device.

    Idempotent: if the device is already revoked, the original timestamp
    is preserved (audit-friendly — "when was this revoked?" stays stable).
    """
    result = await db.execute(
        select(SignageDevice).where(SignageDevice.id == device_id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="device not found"
        )
    if device.revoked_at is None:
        await db.execute(
            update(SignageDevice)
            .where(SignageDevice.id == device_id)
            .values(revoked_at=func.now())
        )
        await db.commit()
    # else: idempotent no-op — original revoked_at preserved on repeat calls.
    return None
