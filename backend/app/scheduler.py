"""APScheduler integration for Personio sync AND v1.15 sensor polling.

Decisions (preserved from v1.3 and extended in v1.15):
  D-05 (v1.3): In-process AsyncIOScheduler under FastAPI lifespan, in-memory jobstore.
  D-06 (v1.3): Interval changes take effect immediately via reschedule.
  D-07 (v1.3): manual-only (interval == 0) removes the scheduled job.
  SEN-SCH-01..06 (v1.15): single scheduler, shared SnmpEngine, max_instances=1,
    coalesce=True, misfire_grace_time=30, outer asyncio.wait_for, daily retention
    cleanup at 03:00 UTC, reschedule helper for Phase 40 admin settings endpoint.

PITFALLS addressed:
  C-1: single shared SnmpEngine on app.state.snmp_engine — no per-call instantiation.
  C-4: max_instances=1, coalesce=True, misfire_grace_time=30 + outer wait_for.
  C-7: deployment-time --workers 1 invariant lives in docker-compose.yml comment.
  M-7: daily retention cleanup + per-table autovacuum knobs set in 38-01 migration.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from pysnmp.hlapi.v3arch.asyncio import SnmpEngine
from sqlalchemy import delete, select, update
from sqlalchemy.sql import func

from app.database import AsyncSessionLocal
from app.services import signage_pg_listen
from app.models import (
    AppSettings,
    SensorPollLog,
    SensorReading,
    SignageMedia,
    SignagePairingSession,
)
from app.models.signage import SignageDevice, SignageHeartbeatEvent

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
SYNC_JOB_ID = "personio_sync"  # existing — unchanged
SENSOR_POLL_JOB_ID = "sensor_poll"  # NEW (v1.15)
SENSOR_RETENTION_JOB_ID = "sensor_retention_cleanup"  # NEW (v1.15)
PAIRING_CLEANUP_JOB_ID = "signage_pairing_cleanup"  # NEW (v1.16 Phase 42-03)
HEARTBEAT_SWEEPER_JOB_ID = "signage_heartbeat_sweeper"  # NEW (v1.16 Phase 43-04)
ATR_SCAN_JOB_ID = "atr_scan"  # NEW (Phase C)

# OQ-5 fixed retention; not admin-configurable in v1.15 (SEN-SCH-06 / SEN-FUTURE-01).
SENSOR_RETENTION_DAYS = 90

# SGN-SCH-02: pairing sessions older than this cutoff get swept nightly.
# 24h grace sits comfortably outside the 10-minute TTL a kiosk might still be
# polling and leaves the delete-on-deliver path (Plan 42-02) untouched.
PAIRING_CLEANUP_GRACE_HOURS = 24

# SGN-SCH-03 / D-09: PPTX rows older than this in 'processing' at startup are
# abandoned (flipped to 'failed / abandoned_on_restart'). Fail-forward only —
# admin must POST /reconvert explicitly to retry.
PPTX_STUCK_AGE_MINUTES = 5

# Module-level engine reference. Populated in lifespan; read by the scheduled
# poll runner. Not a true public API — routers should use
# request.app.state.snmp_engine, which is set to this same object.
# This trick avoids pickling SnmpEngine as APScheduler kwargs (MemoryJobStore
# pickles by default and SnmpEngine may not pickle cleanly).
_engine: SnmpEngine | None = None


# ---------------------------------------------------------------------------
# Personio sync (existing — unchanged)
# ---------------------------------------------------------------------------

async def _load_sync_interval() -> int:
    """Read personio_sync_interval_h from AppSettings singleton."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.personio_sync_interval_h).where(AppSettings.id == 1)
        )
        return result.scalar_one_or_none() or 0


async def _run_scheduled_sync() -> None:
    """Scheduled job entry point — opens its own session (not FastAPI Depends)."""
    from app.services import hr_sync
    async with AsyncSessionLocal() as session:
        try:
            await hr_sync.run_sync(session)
        except Exception:
            pass  # sync meta already updated with error status inside run_sync


# Feste Anker-Uhrzeit für den Personio-Sync (02:00 UTC ≈ 03:00/04:00 lokal, im
# ruhigen Nachtfenster). Der Anker macht aus dem 24h-Intervall einen Lauf zu einer
# FESTEN Uhrzeit statt "letzter Start + 24h": so überspringt der Sync auch bei
# häufigen API-Neustarts keinen Tag mehr (das Requirement „täglich").
PERSONIO_SYNC_ANCHOR = datetime(2020, 1, 1, 2, 0, tzinfo=timezone.utc)


def schedule_personio_sync(interval_h: int) -> None:
    """Personio-Sync-Job registrieren/entfernen (D-06 sofort wirksam, D-07 manual-only).

    ``interval_h == 0`` → kein geplanter Job (nur manuell). ``> 0`` → Intervall-Job,
    an :data:`PERSONIO_SYNC_ANCHOR` verankert, damit ein 24h-Intervall zuverlässig
    zur festen Uhrzeit feuert. Wird sowohl beim Start (Lifespan) als auch bei
    Intervall-Änderungen (PUT /api/settings) aufgerufen. Wirft nie.
    """
    try:
        existing = scheduler.get_job(SYNC_JOB_ID)
        if interval_h <= 0:
            if existing is not None:
                scheduler.remove_job(SYNC_JOB_ID)
                log.info("personio_sync entfernt (manual-only)")
            return
        scheduler.add_job(
            _run_scheduled_sync,
            trigger=IntervalTrigger(hours=interval_h, start_date=PERSONIO_SYNC_ANCHOR),
            id=SYNC_JOB_ID,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,  # verpasste Läufe (Downtime) bis 1h später nachholen
        )
        job = scheduler.get_job(SYNC_JOB_ID)
        log.info(
            "personio_sync geplant: interval_h=%s next_run=%s",
            interval_h,
            job.next_run_time.isoformat() if job and job.next_run_time else None,
        )
    except Exception:
        log.exception("schedule_personio_sync fehlgeschlagen (interval_h=%s)", interval_h)


# ---------------------------------------------------------------------------
# Sensor polling (v1.15)
# ---------------------------------------------------------------------------

async def _load_sensor_interval() -> int:
    """Read AppSettings.sensor_poll_interval_s. Default 60 per schema; 0 disables."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.sensor_poll_interval_s).where(AppSettings.id == 1)
        )
        value = result.scalar_one_or_none()
    # Row exists with default 60 by migration; None only on a totally unseeded DB.
    return int(value) if value is not None else 60


async def _run_scheduled_sensor_poll() -> None:
    """APScheduler entry point — opens own session, uses module-level engine.

    PITFALLS C-4: outer asyncio.wait_for with timeout = min(45, interval-5).
    Never raises — any exception is swallowed with a log.exception so the
    scheduler keeps ticking on the next interval.
    """
    from app.services import snmp_poller
    if _engine is None:
        log.warning("sensor_poll skipped — SnmpEngine not initialized on app.state")
        return
    interval_s = await _load_sensor_interval()
    inner_timeout = max(5, min(45, interval_s - 5))
    async with AsyncSessionLocal() as session:
        try:
            await asyncio.wait_for(
                snmp_poller.poll_all(session, _engine, manual=False),
                timeout=inner_timeout,
            )
        except asyncio.TimeoutError:
            log.warning("sensor_poll exceeded %ss timeout", inner_timeout)
        except Exception:
            log.exception("sensor_poll runner failed")


async def _run_sensor_retention_cleanup() -> None:
    """Daily delete of sensor_readings + sensor_poll_log older than 90 days.

    Fixed retention per OQ-5 / SEN-SCH-06. Not admin-configurable in v1.15.
    Runs at 03:00 UTC via CronTrigger (low-traffic window, parallels the
    nightly pg_dump sidecar).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=SENSOR_RETENTION_DAYS)
    async with AsyncSessionLocal() as session:
        try:
            readings_del = await session.execute(
                delete(SensorReading).where(SensorReading.recorded_at < cutoff)
            )
            poll_log_del = await session.execute(
                delete(SensorPollLog).where(SensorPollLog.attempted_at < cutoff)
            )
            await session.commit()
            log.info(
                "sensor_retention_cleanup: deleted readings=%d poll_log=%d cutoff=%s",
                readings_del.rowcount,
                poll_log_del.rowcount,
                cutoff.isoformat(),
            )
        except Exception:
            log.exception("sensor_retention_cleanup failed")
            await session.rollback()


async def _run_signage_pairing_cleanup() -> None:
    """D-12: delete expired pairing sessions older than 24h.

    D-13: This cron carries the expiration invariant for SGN-DB-02.
    Phase 41 dropped ``expires_at > now()`` from the partial-unique index
    predicate because Postgres forbids ``now()`` in IMMUTABLE partial
    predicates (errcode 42P17). Without this cron, expired-but-unclaimed
    codes stay in the unique index indefinitely and ``/pair/request`` will
    eventually trip the 5-retry saturation path. This is correctness,
    not cosmetics.

    Predicate is ``expires_at < now() - 24h`` only — claim-state is
    irrelevant. Claimed rows are either already gone (delete-on-deliver
    in Plan 42-02's GET /status) or stuck because a kiosk never polled;
    either way the 24h grace window is ample.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=PAIRING_CLEANUP_GRACE_HOURS)
    async with AsyncSessionLocal() as session:
        try:
            result = await asyncio.wait_for(
                session.execute(
                    delete(SignagePairingSession).where(
                        SignagePairingSession.expires_at < cutoff
                    )
                ),
                timeout=30,
            )
            await session.commit()
            log.info(
                "signage_pairing_cleanup: deleted sessions=%d cutoff=%s",
                result.rowcount,
                cutoff.isoformat(),
            )
        except Exception:
            log.exception("signage_pairing_cleanup failed")
            await session.rollback()


async def _run_signage_heartbeat_sweeper() -> None:
    """SGN-SCH-01 / D-15: flip stale signage devices to offline.

    Runs every minute. For every device whose last_seen_at is older than
    5 minutes and is not already offline and is not revoked, set
    ``status = 'offline'``. Idempotent — already-offline devices are
    excluded so the rowcount stays truthy only on state transitions.

    D-10 note: GET /playlist does NOT touch last_seen_at; heartbeat does.
    This job therefore observes real kiosk liveness, not polling activity.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await asyncio.wait_for(
                session.execute(
                    update(SignageDevice)
                    .where(
                        SignageDevice.last_seen_at
                        < func.now() - timedelta(minutes=5),
                        SignageDevice.status != "offline",
                        SignageDevice.revoked_at.is_(None),
                    )
                    .values(status="offline", updated_at=func.now())
                ),
                timeout=20,
            )
            # Phase 53 SGN-ANA-01 (D-03): 25 h rolling retention — 1 h buffer past
            # the 24 h analytics horizon so rows near the boundary don't get pruned
            # out from under the /devices/analytics query. Single DELETE; one commit
            # covers both the device-status flip above and this prune.
            prune_result = await asyncio.wait_for(
                session.execute(
                    delete(SignageHeartbeatEvent).where(
                        SignageHeartbeatEvent.ts < func.now() - timedelta(hours=25)
                    )
                ),
                timeout=20,
            )
            await session.commit()
            log.info(
                "signage_heartbeat_sweeper: flipped devices=%d pruned_events=%d",
                result.rowcount,
                prune_result.rowcount,
            )
        except Exception:
            log.exception("signage_heartbeat_sweeper failed")
            await session.rollback()


async def _run_pptx_stuck_reset() -> None:
    """SGN-SCH-03 / D-09 + D-18: one-shot startup reset of stuck PPTX rows.

    Flips any signage_media row that was 'processing' more than 5 minutes
    ago (by conversion_started_at) into a terminal 'failed' state with
    conversion_error='abandoned_on_restart'. Fail-forward — admin must
    call POST /api/signage/media/{id}/reconvert explicitly to retry.

    Runs ONCE at scheduler init, before the cron/interval jobs are
    registered. Idempotent — a clean DB is a no-op (DEBUG log). Non-zero
    resets are logged at INFO.

    Predicate: conversion_status == 'processing' AND conversion_started_at
    < cutoff. Rows with conversion_started_at IS NULL never satisfy the
    strict-less-than comparison in SQL, so a 'processing' row missing a
    timestamp (data bug) is naturally excluded rather than silently flipped.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=PPTX_STUCK_AGE_MINUTES)
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                update(SignageMedia)
                .where(
                    SignageMedia.conversion_status == "processing",
                    SignageMedia.conversion_started_at < cutoff,
                )
                .values(
                    conversion_status="failed",
                    conversion_error="abandoned_on_restart",
                )
            )
            await session.commit()
            reset_count = result.rowcount or 0
            if reset_count > 0:
                log.info(
                    "pptx_stuck_reset: flipped rows=%d cutoff=%s",
                    reset_count,
                    cutoff.isoformat(),
                )
            else:
                log.debug(
                    "pptx_stuck_reset: no stuck rows (cutoff=%s)",
                    cutoff.isoformat(),
                )
        except Exception:
            log.exception("pptx_stuck_reset failed")
            await session.rollback()


async def _load_atr_interval() -> int:
    async with AsyncSessionLocal() as session:
        v = (await session.execute(
            select(AppSettings.atr_scan_interval_s).where(AppSettings.id == 1)
        )).scalar_one_or_none()
    return int(v) if v is not None else 0


async def _run_atr_scan() -> None:
    """List new Lieferscheine on the SMB share and process each (Phase C)."""
    from app.models import AppSettings, AtrDelivery
    from app.services import atr_fileserver as fs
    from app.services.atr_deliver import generate_and_deliver
    from app.services.atr_lieferschein import parse_lieferschein
    from app.services.atr_match import match_positions

    async with AsyncSessionLocal() as session:
        row = (await session.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one_or_none()
        if row is None or row.atr_scan_interval_s == 0:
            return
        cfg = fs.smb_config_from_settings(row)
        if cfg is None:
            return
        try:
            names = await asyncio.wait_for(asyncio.to_thread(fs.list_input_pdfs, cfg), timeout=60)
        except (fs.AtrFileserverError, asyncio.TimeoutError):
            log.warning("atr_scan: list_input_pdfs failed/timed out", exc_info=True)
            return
        # Skip names with an OPEN (draft) scan delivery still awaiting review —
        # prevents re-creating a draft every tick while the file waits in Input.
        # Once a delivery has moved past draft (generated/delivered), a same-named
        # file reappearing in Input is a deliberate re-drop (or a delivery/archive
        # that never moved it out) and gets processed again — otherwise a filename
        # is silently ignored forever the moment it is first processed.
        open_drafts = set((await session.execute(
            select(AtrDelivery.source_filename).where(
                AtrDelivery.origin == "scan", AtrDelivery.status == "draft")
        )).scalars().all())
        for name in names:
            if name in open_drafts:
                log.debug("atr_scan: %s skipped — open draft awaiting review", name)
                continue
            try:
                raw = await asyncio.wait_for(asyncio.to_thread(fs.read_input, cfg, name), timeout=60)
                parsed = await parse_lieferschein(raw)
                if not parsed.positions:
                    log.warning("atr_scan: no positions in %s; skipping", name)
                    continue
                md = await match_positions(session, parsed, name)
                from app.routers.atr_delivery import _persist_draft  # reuse the draft builder
                delivery = await _persist_draft(session, md)
                delivery.origin = "scan"
                delivery.source_path = f"{cfg.input_path}/{name}"
                await session.commit()
                if row.atr_auto_mode:
                    try:
                        from sqlalchemy.orm import selectinload
                        d = (await session.execute(
                            select(AtrDelivery).options(selectinload(AtrDelivery.items)).where(AtrDelivery.id == delivery.id)
                        )).scalar_one()
                        await generate_and_deliver(session, d, row)
                    except Exception:
                        log.exception("atr_scan: auto-generate failed for %s; deleting draft to retry next scan", name)
                        await session.delete(delivery)
                        await session.commit()
            except Exception:
                log.exception("atr_scan: failed processing %s", name)
                await session.rollback()


def reschedule_atr_scan(new_interval_s: int) -> None:
    try:
        existing = scheduler.get_job(ATR_SCAN_JOB_ID)
        if new_interval_s <= 0:
            if existing is not None:
                scheduler.remove_job(ATR_SCAN_JOB_ID)
            return
        if existing is None:
            scheduler.add_job(_run_atr_scan, trigger="interval", seconds=new_interval_s,
                              id=ATR_SCAN_JOB_ID, replace_existing=True, max_instances=1,
                              coalesce=True, misfire_grace_time=30)
        else:
            scheduler.reschedule_job(ATR_SCAN_JOB_ID, trigger="interval", seconds=new_interval_s)
        job = scheduler.get_job(ATR_SCAN_JOB_ID)
        log.info("atr_scan rescheduled: new=%ss next_run=%s", new_interval_s,
                 job.next_run_time.isoformat() if job and job.next_run_time else None)
    except Exception:
        log.exception("reschedule_atr_scan failed (new_interval_s=%s)", new_interval_s)


def reschedule_sensor_poll(new_interval_s: int) -> None:
    """Phase 40 admin-settings hook — re-pins sensor_poll to a new interval.

    Contract (SEN-SCH-04):
      - new_interval_s > 0 and job exists → reschedule_job(SENSOR_POLL_JOB_ID, ...).
      - new_interval_s > 0 and job missing → add_job with full guardrail kwargs.
      - new_interval_s <= 0 → remove the job entirely (matches Personio D-07:
        manual-only means no scheduled job, not a paused one).

    Logs old interval → new interval → computed next_run_time. All failures are
    caught and logged; the helper never raises so a broken PUT /api/settings
    request path doesn't leak scheduler internals to the admin UI.
    """
    try:
        existing = scheduler.get_job(SENSOR_POLL_JOB_ID)
        old_interval = (
            existing.trigger.interval.total_seconds() if existing else None
        )
        if new_interval_s <= 0:
            if existing is not None:
                scheduler.remove_job(SENSOR_POLL_JOB_ID)
                log.info(
                    "sensor_poll removed (old_interval=%s, new=0/disabled)",
                    old_interval,
                )
            return
        if existing is None:
            scheduler.add_job(
                _run_scheduled_sensor_poll,
                trigger="interval",
                seconds=new_interval_s,
                id=SENSOR_POLL_JOB_ID,
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=30,
            )
        else:
            scheduler.reschedule_job(
                SENSOR_POLL_JOB_ID,
                trigger="interval",
                seconds=new_interval_s,
            )
        job = scheduler.get_job(SENSOR_POLL_JOB_ID)
        log.info(
            "sensor_poll rescheduled: old=%ss new=%ss next_run=%s",
            old_interval,
            new_interval_s,
            job.next_run_time.isoformat() if job and job.next_run_time else None,
        )
    except Exception:
        log.exception(
            "reschedule_sensor_poll failed (new_interval_s=%s)", new_interval_s
        )


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan — starts/stops APScheduler + populates shared SnmpEngine."""
    global _engine
    app.state.scheduler = scheduler

    # v1.15: single shared SnmpEngine (PITFALLS C-1 / SEN-BE-03). Populated
    # before scheduler.start() so both scheduler jobs and HTTP routes read
    # the same engine instance.
    _engine = SnmpEngine()
    app.state.snmp_engine = _engine

    # --- Personio sync ---
    # An feste Uhrzeit verankert; registriert NACH scheduler.start() (weiter unten),
    # damit next_run_time sofort feststeht und geloggt werden kann.

    # --- Sensor poll (v1.15) ---
    sensor_interval_s = await _load_sensor_interval()
    if sensor_interval_s > 0:
        scheduler.add_job(
            _run_scheduled_sensor_poll,
            trigger="interval",
            seconds=sensor_interval_s,
            id=SENSOR_POLL_JOB_ID,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=30,
        )

    # --- ATR scan (Phase C) ---
    atr_interval_s = await _load_atr_interval()
    if atr_interval_s > 0:
        scheduler.add_job(_run_atr_scan, trigger="interval", seconds=atr_interval_s,
                          id=ATR_SCAN_JOB_ID, replace_existing=True, max_instances=1,
                          coalesce=True, misfire_grace_time=30)

    # --- Sensor retention cleanup (daily at 03:00 UTC — v1.15) ---
    scheduler.add_job(
        _run_sensor_retention_cleanup,
        trigger=CronTrigger(hour=3, minute=0, timezone=timezone.utc),
        id=SENSOR_RETENTION_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,  # daily job — 5min grace is fine
    )

    # --- Signage pairing cleanup (daily at 03:00 UTC — v1.16 Phase 42-03) ---
    # SGN-SCH-02 + D-13: carries expiration invariant for SGN-DB-02 (see
    # _run_signage_pairing_cleanup docstring). Registered alongside the v1.15
    # sensor_retention_cleanup; both jobs sit in the 03:00 UTC low-traffic slot.
    scheduler.add_job(
        _run_signage_pairing_cleanup,
        trigger=CronTrigger(hour=3, minute=0, timezone=timezone.utc),
        id=PAIRING_CLEANUP_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    log.info("registered signage_pairing_cleanup cron (03:00 UTC)")

    # --- Signage heartbeat sweeper (1-min interval — v1.16 Phase 43-04) ---
    # SGN-SCH-01 / D-15: flips stale devices (last_seen_at < now - 5min) to
    # offline. max_instances=1 + coalesce=True matches the --workers 1
    # invariant (cross-cutting hazard #4) and the v1.15 sensor-poll shape.
    scheduler.add_job(
        _run_signage_heartbeat_sweeper,
        trigger="interval",
        minutes=1,
        id=HEARTBEAT_SWEEPER_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
    )
    log.info("registered signage_heartbeat_sweeper (1-min interval)")

    # --- PPTX stuck-row reset (one-shot at startup — v1.16 Phase 44) ---
    # SGN-SCH-03 / D-09 + D-18: flips 'processing' rows older than 5 min to
    # 'failed / abandoned_on_restart'. Runs BEFORE scheduler.start() so the
    # reset happens exactly once and does not race interval jobs. Not a
    # scheduled job — not registered with add_job.
    await _run_pptx_stuck_reset()
    log.info("pptx_stuck_reset hook executed")

    scheduler.start()
    # Personio-Sync an fester Uhrzeit registrieren (nach start(), s. o.).
    schedule_personio_sync(await _load_sync_interval())
    await signage_pg_listen.start(app)
    try:
        yield
    finally:
        await signage_pg_listen.stop(app)
        scheduler.shutdown()
        _engine = None
        app.state.snmp_engine = None
