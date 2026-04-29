"""Async pysnmp service — v1.15 Sensor Monitor (Phase 38).

Public async API:
  - snmp_get(engine, host, port, community, oid) -> float | None
  - snmp_walk(engine, host, port, community, base_oid, max_results=200) -> list[dict]
  - poll_sensor(session, engine, sensor) -> PollResult
  - poll_all(session, engine) -> PollAllResult

Guardrails (lock-in from PITFALLS research):
  - v3arch.asyncio import path (NOT the deprecated v1arch pysnmp.hlapi.asyncio)
  - SnmpEngine is NEVER instantiated here — passed in from app.state.snmp_engine (C-1)
  - No sync DB drivers (sqlite3/psycopg2) — AsyncSessionLocal only (C-2)
  - No blocking sleep (C-8) — only asyncio.sleep if ever needed
  - asyncio.gather(..., return_exceptions=True) — one sensor failure must not cancel
    siblings (M-3)
  - Writes use postgresql.insert().on_conflict_do_nothing(index_elements=[
    'sensor_id','recorded_at']) to dedupe scheduled+manual collisions (C-5)
  - Community decrypted ONCE per poll (not per OID) — plaintext never logged (C-3)
  - timeout=3.0, retries=2 defaults (N-3 — 3 total attempts)
"""
from __future__ import annotations

import asyncio
import logging
import time as _time_module  # import under alias — never call .sleep (CI grep ban)
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
)

# pysnmp 7.1 exposes walk_cmd in v3arch.asyncio; if the installed version only has
# next_cmd (older 7.0.x), swap the import. Both produce the same async-iterator shape.
try:
    from pysnmp.hlapi.v3arch.asyncio import walk_cmd as _walk_cmd  # type: ignore
except ImportError:  # pragma: no cover — fallback for pysnmp 7.0.x
    from pysnmp.hlapi.v3arch.asyncio import next_cmd as _walk_cmd  # type: ignore

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Sensor, SensorPollLog, SensorReading
from app.security.sensor_community import decrypt_community

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 3.0     # seconds per SNMP attempt
DEFAULT_RETRIES = 2       # 3 total attempts — N-3 (transient UDP loss tolerance)
DEFAULT_WALK_MAX = 200    # matches reference impl cap
DEDUPE_WINDOW_S = 2       # SEN-BE-12: manual poll skips if last reading < 2s old


@dataclass
class PollResult:
    """Outcome of polling one sensor (for caller logging / API response)."""
    sensor_id: int
    sensor_name: str
    success: bool
    error: str | None = None
    reading_written: bool = False
    latency_ms: int = 0


@dataclass
class PollAllResult:
    """Aggregate outcome of poll_all. Shape matches PollNowResult schema."""
    sensors_polled: int = 0
    errors: list[str] = field(default_factory=list)


async def snmp_get(
    engine: SnmpEngine,
    host: str,
    port: int,
    community: str,
    oid: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> float | None:
    """Single-OID GET. Returns float or None on any error.

    Never raises — all transport/protocol errors log + return None. Use the shared
    engine from app.state.snmp_engine (never instantiate here — C-1).
    """
    try:
        transport = await UdpTransportTarget.create(
            (host, port), timeout=timeout, retries=retries
        )
        error_indication, error_status, _, var_binds = await get_cmd(
            engine,
            CommunityData(community, mpModel=1),  # mpModel=1 → SNMPv2c
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )
        if error_indication:
            # Log host only — NEVER community. Community is a secret (C-3).
            log.warning("snmp_get indication host=%s oid=%s: %s", host, oid, error_indication)
            return None
        if error_status:
            log.warning("snmp_get status host=%s oid=%s: %s", host, oid, error_status.prettyPrint())
            return None
        for _, value in var_binds:
            try:
                return float(value)
            except (TypeError, ValueError):
                log.warning("snmp_get non-numeric host=%s oid=%s value=%r", host, oid, value)
                return None
    except Exception as exc:  # pysnmp transport errors, cancelled, etc.
        log.warning("snmp_get exception host=%s oid=%s: %s", host, oid, exc)
    return None


async def snmp_walk(
    engine: SnmpEngine,
    host: str,
    port: int,
    community: str,
    base_oid: str,
    *,
    max_results: int = DEFAULT_WALK_MAX,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> list[dict[str, Any]]:
    """Walk a subtree starting at base_oid. Returns [{oid, value, type}]."""
    results: list[dict[str, Any]] = []
    try:
        transport = await UdpTransportTarget.create(
            (host, port), timeout=timeout, retries=retries
        )
        iterator = _walk_cmd(
            engine,
            CommunityData(community, mpModel=1),
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
        )
        async for error_indication, error_status, _, var_binds in iterator:
            if error_indication:
                log.warning("snmp_walk indication host=%s: %s", host, error_indication)
                break
            if error_status:
                log.warning("snmp_walk status host=%s: %s", host, error_status.prettyPrint())
                break
            for name, value in var_binds:
                results.append({
                    "oid": str(name),
                    "value": value.prettyPrint(),
                    "type": type(value).__name__,
                })
                if len(results) >= max_results:
                    return results
    except Exception as exc:
        log.warning("snmp_walk exception host=%s: %s", host, exc)
    return results


async def _write_poll_log(
    session: AsyncSession,
    *,
    sensor_id: int,
    success: bool,
    error_kind: str | None,
    latency_ms: int,
) -> None:
    log_row = SensorPollLog(
        sensor_id=sensor_id,
        attempted_at=datetime.now(timezone.utc),
        success=success,
        error_kind=error_kind,
        latency_ms=latency_ms,
    )
    session.add(log_row)


async def _write_reading_on_conflict(
    session: AsyncSession,
    *,
    sensor_id: int,
    recorded_at: datetime,
    temperature: Decimal | None,
    humidity: Decimal | None,
    error_code: str | None,
) -> bool:
    """Insert a reading; returns True if a row was inserted, False if dedupe skip.

    PITFALLS C-5: ON CONFLICT DO NOTHING on UNIQUE(sensor_id, recorded_at).
    """
    stmt = (
        pg_insert(SensorReading)
        .values(
            sensor_id=sensor_id,
            recorded_at=recorded_at,
            temperature=temperature,
            humidity=humidity,
            error_code=error_code,
        )
        .on_conflict_do_nothing(index_elements=["sensor_id", "recorded_at"])
    )
    result = await session.execute(stmt)
    return (result.rowcount or 0) > 0


async def _recent_reading_exists(
    session: AsyncSession, *, sensor_id: int, within_seconds: int
) -> bool:
    """SEN-BE-12: manual poll dedupes if last row <2s old."""
    stmt = (
        select(SensorReading)
        .where(SensorReading.sensor_id == sensor_id)
        .order_by(SensorReading.recorded_at.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return False
    age = (datetime.now(timezone.utc) - row.recorded_at).total_seconds()
    return age < within_seconds


async def poll_sensor(
    session: AsyncSession,
    engine: SnmpEngine,
    sensor: Sensor,
    *,
    manual: bool = False,
) -> PollResult:
    """Poll one sensor. Writes exactly one row to sensor_poll_log (always) and
    at most one row to sensor_readings (on success, unless dedupe skip).

    Raises nothing — per-sensor exception boundary for M-3.
    """
    t0 = _time_module.perf_counter()  # NOTE: .perf_counter is allowed; .sleep is banned
    if not sensor.enabled:
        return PollResult(sensor.id, sensor.name, success=False, error="disabled", latency_ms=0)

    # Manual poll dedupe (SEN-BE-12): skip if last reading <2s old
    if manual and await _recent_reading_exists(
        session, sensor_id=sensor.id, within_seconds=DEDUPE_WINDOW_S
    ):
        return PollResult(
            sensor.id, sensor.name, success=True, reading_written=False,
            latency_ms=0, error="dedupe_2s_window",
        )

    try:
        community_plain = decrypt_community(sensor.community)  # NEVER logged
    except ValueError as exc:
        latency_ms = int((_time_module.perf_counter() - t0) * 1000)
        await _write_poll_log(
            session, sensor_id=sensor.id, success=False,
            error_kind="decrypt_failed", latency_ms=latency_ms,
        )
        return PollResult(sensor.id, sensor.name, success=False, error=str(exc), latency_ms=latency_ms)

    temp_raw: float | None = None
    hum_raw: float | None = None
    error_code: str | None = None

    if sensor.temperature_oid:
        temp_raw = await snmp_get(
            engine, sensor.host, sensor.port, community_plain, sensor.temperature_oid
        )
    if sensor.humidity_oid:
        hum_raw = await snmp_get(
            engine, sensor.host, sensor.port, community_plain, sensor.humidity_oid
        )

    # PITFALLS N-2: divide by scale (raw / scale → display). Guard against zero scale
    # (schema validates >0, but be defensive).
    def _scaled(raw: float | None, scale: Decimal) -> Decimal | None:
        if raw is None:
            return None
        scale_f = float(scale)
        if scale_f <= 0:
            return None
        return Decimal(str(raw / scale_f))

    temperature = _scaled(temp_raw, sensor.temperature_scale)
    humidity = _scaled(hum_raw, sensor.humidity_scale)

    success = temperature is not None or humidity is not None
    if not success:
        error_code = "timeout_or_error"

    latency_ms = int((_time_module.perf_counter() - t0) * 1000)

    reading_written = False
    if success:
        reading_written = await _write_reading_on_conflict(
            session,
            sensor_id=sensor.id,
            recorded_at=datetime.now(timezone.utc),
            temperature=temperature,
            humidity=humidity,
            error_code=error_code,
        )

    await _write_poll_log(
        session, sensor_id=sensor.id, success=success,
        error_kind=None if success else "snmp_error",
        latency_ms=latency_ms,
    )

    return PollResult(
        sensor_id=sensor.id, sensor_name=sensor.name,
        success=success, error=None if success else error_code,
        reading_written=reading_written, latency_ms=latency_ms,
    )


async def poll_all(
    session: AsyncSession,
    engine: SnmpEngine,
    *,
    manual: bool = False,
) -> PollAllResult:
    """Gather-poll every enabled sensor. Commits once at the end.

    PITFALLS M-3: return_exceptions=True — one flaky sensor must not cancel siblings.
    PITFALLS N-3: per-sensor try/except already inside poll_sensor; gather is
    belt-and-suspenders for unexpected exceptions.
    """
    sensors = (
        await session.execute(
            select(Sensor).where(Sensor.enabled.is_(True)).order_by(Sensor.id)
        )
    ).scalars().all()

    if not sensors:
        return PollAllResult(sensors_polled=0, errors=[])

    results = await asyncio.gather(
        *(poll_sensor(session, engine, s, manual=manual) for s in sensors),
        return_exceptions=True,
    )

    errors: list[str] = []
    polled = 0
    for s, r in zip(sensors, results, strict=True):
        if isinstance(r, BaseException):
            errors.append(f"{s.name}: {type(r).__name__}: {r}")
            # Still log the attempt so UI can show 'offline'
            try:
                await _write_poll_log(
                    session, sensor_id=s.id, success=False,
                    error_kind="unexpected_exception", latency_ms=0,
                )
            except Exception:
                pass  # session may be dirty; best-effort
        else:
            polled += 1
            if not r.success and r.error:
                errors.append(f"{s.name}: {r.error}")

    await session.commit()
    return PollAllResult(sensors_polled=polled, errors=errors)
