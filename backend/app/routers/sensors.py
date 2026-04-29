"""/api/sensors/* — admin-gated sensor CRUD, readings, poll, probe, walk, status.

Router-level admin gate (PITFALLS M-1): every endpoint requires Admin role.
The dep-audit test in tests/test_sensors_admin_gate.py enforces this.

Endpoints:
  GET    /api/sensors             -> list SensorRead (community OMITTED)
  POST   /api/sensors             -> create (SensorCreate; community SecretStr encrypted on write)
  PATCH  /api/sensors/{id}        -> update (SensorUpdate; partial)
  DELETE /api/sensors/{id}        -> delete (cascades readings + poll_log via FK)
  GET    /api/sensors/{id}/readings?hours=N  -> list SensorReadingRead
  POST   /api/sensors/poll-now    -> PollNowResult (wait_for timeout=30)
  POST   /api/sensors/snmp-probe  -> live temp+humidity for an uncommitted draft
  POST   /api/sensors/snmp-walk   -> list of {oid, value, type}
  GET    /api/sensors/status      -> per-sensor health from sensor_poll_log

Scheduler integration lives in Plan 38-03 — this plan does NOT touch scheduler.py.
The router reads `request.app.state.snmp_engine`; 38-03 populates that attribute
in the lifespan hook.

Compute-justified: clause 2 (Fernet community write-side) + clause 1 (SNMP polling).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import Sensor, SensorPollLog, SensorReading
from app.schemas import (
    PollNowResult,
    SensorCreate,
    SensorRead,
    SensorReadingRead,
    SensorUpdate,
    SnmpProbeRequest,
    SnmpWalkRequest,
)
from app.security.directus_auth import get_current_user, require_admin
from app.security.sensor_community import encrypt_community
from app.services import snmp_poller

router = APIRouter(
    prefix="/api/sensors",
    tags=["sensors"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine_from_request(request: Request):
    """Read the shared SnmpEngine from app.state. Set in lifespan by 38-03."""
    engine = getattr(request.app.state, "snmp_engine", None)
    if engine is None:
        raise HTTPException(503, "SNMP engine not initialized")
    return engine


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[SensorRead])
async def list_sensors(db: AsyncSession = Depends(get_async_db_session)) -> list[Sensor]:
    result = await db.execute(select(Sensor).order_by(Sensor.id))
    return list(result.scalars().all())


@router.post("", response_model=SensorRead, status_code=201)
async def create_sensor(
    payload: SensorCreate, db: AsyncSession = Depends(get_async_db_session)
) -> Sensor:
    now = datetime.now(timezone.utc)
    row = Sensor(
        name=payload.name,
        host=payload.host,
        port=payload.port,
        community=encrypt_community(payload.community.get_secret_value()),
        temperature_oid=payload.temperature_oid,
        humidity_oid=payload.humidity_oid,
        temperature_scale=payload.temperature_scale,
        humidity_scale=payload.humidity_scale,
        enabled=payload.enabled,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "sensor with this name already exists") from exc
    await db.refresh(row)
    return row


@router.patch("/{sensor_id}", response_model=SensorRead)
async def update_sensor(
    sensor_id: int,
    payload: SensorUpdate,
    db: AsyncSession = Depends(get_async_db_session),
) -> Sensor:
    row = (
        await db.execute(select(Sensor).where(Sensor.id == sensor_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "sensor not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "community" in update_data and update_data["community"] is not None:
        # payload.community is SecretStr here (Pydantic); pull plaintext only at
        # the encrypt call site, then drop the reference (C-3).
        update_data["community"] = encrypt_community(
            payload.community.get_secret_value()
        )
    for k, v in update_data.items():
        setattr(row, k, v)
    row.updated_at = datetime.now(timezone.utc)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "sensor name conflict") from exc
    await db.refresh(row)
    return row


@router.delete("/{sensor_id}", status_code=204)
async def delete_sensor(
    sensor_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> None:
    result = await db.execute(delete(Sensor).where(Sensor.id == sensor_id))
    if result.rowcount == 0:
        raise HTTPException(404, "sensor not found")
    await db.commit()


# ---------------------------------------------------------------------------
# Readings
# ---------------------------------------------------------------------------


@router.get("/{sensor_id}/readings", response_model=list[SensorReadingRead])
async def get_readings(
    sensor_id: int,
    hours: int = 24,
    db: AsyncSession = Depends(get_async_db_session),
) -> list[SensorReading]:
    if hours < 1 or hours > 24 * 365:
        raise HTTPException(422, "hours must be between 1 and 8760")
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = (
        select(SensorReading)
        .where(
            SensorReading.sensor_id == sensor_id,
            SensorReading.recorded_at >= since,
        )
        .order_by(SensorReading.recorded_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# Poll / Probe / Walk
# ---------------------------------------------------------------------------


@router.post("/poll-now", response_model=PollNowResult)
async def poll_now(
    request: Request,
    db: AsyncSession = Depends(get_async_db_session),
) -> PollNowResult:
    """SEN-BE-10: blocking await with asyncio.wait_for(timeout=30)."""
    engine = _engine_from_request(request)
    try:
        result = await asyncio.wait_for(
            snmp_poller.poll_all(db, engine, manual=True),
            timeout=30,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, "poll-now exceeded 30s timeout") from exc
    return PollNowResult(
        sensors_polled=result.sensors_polled, errors=result.errors
    )


@router.post("/snmp-probe", response_model=dict)
async def snmp_probe(
    payload: SnmpProbeRequest, request: Request
) -> dict[str, Any]:
    """Probe an uncommitted draft config; returns live temp+humidity."""
    engine = _engine_from_request(request)
    community = payload.community.get_secret_value()
    temp: float | None = None
    hum: float | None = None
    if payload.temperature_oid:
        raw = await snmp_poller.snmp_get(
            engine, payload.host, payload.port, community, payload.temperature_oid
        )
        if raw is not None and float(payload.temperature_scale) > 0:
            temp = raw / float(payload.temperature_scale)
    if payload.humidity_oid:
        raw = await snmp_poller.snmp_get(
            engine, payload.host, payload.port, community, payload.humidity_oid
        )
        if raw is not None and float(payload.humidity_scale) > 0:
            hum = raw / float(payload.humidity_scale)
    return {"temperature": temp, "humidity": hum}


@router.post("/snmp-walk", response_model=list[dict])
async def snmp_walk(
    payload: SnmpWalkRequest, request: Request
) -> list[dict[str, Any]]:
    engine = _engine_from_request(request)
    # Overall walk cap — PITFALLS C-8: wrap in asyncio.wait_for so a runaway walk
    # can't freeze the admin UI.
    try:
        return await asyncio.wait_for(
            snmp_poller.snmp_walk(
                engine,
                payload.host,
                payload.port,
                payload.community.get_secret_value(),
                payload.base_oid,
                max_results=payload.max_results,
            ),
            timeout=30,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, "snmp-walk exceeded 30s timeout") from exc


# ---------------------------------------------------------------------------
# Status (per-sensor liveness from sensor_poll_log)
# ---------------------------------------------------------------------------


@router.get("/status", response_model=list[dict])
async def get_status(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[dict[str, Any]]:
    """Per-sensor liveness: last_attempt_at, last_success_at, consecutive_failures."""
    sensors = (await db.execute(select(Sensor).order_by(Sensor.id))).scalars().all()
    statuses: list[dict[str, Any]] = []
    for s in sensors:
        last_attempt = (
            await db.execute(
                select(SensorPollLog)
                .where(SensorPollLog.sensor_id == s.id)
                .order_by(SensorPollLog.attempted_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        last_success = (
            await db.execute(
                select(SensorPollLog)
                .where(SensorPollLog.sensor_id == s.id, SensorPollLog.success.is_(True))
                .order_by(SensorPollLog.attempted_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        # consecutive failures since last success (scan most recent 10 attempts)
        recent = (
            await db.execute(
                select(SensorPollLog)
                .where(SensorPollLog.sensor_id == s.id)
                .order_by(SensorPollLog.attempted_at.desc())
                .limit(10)
            )
        ).scalars().all()
        consecutive_failures = 0
        for r in recent:
            if r.success:
                break
            consecutive_failures += 1
        statuses.append({
            "sensor_id": s.id,
            "sensor_name": s.name,
            "last_attempt_at": last_attempt.attempted_at.isoformat() if last_attempt else None,
            "last_success_at": last_success.attempted_at.isoformat() if last_success else None,
            "consecutive_failures": consecutive_failures,
            "offline": consecutive_failures >= 3,  # PITFALLS N-3: 3-strike threshold
        })
    return statuses
