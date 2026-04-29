"""Scheduler unit tests for v1.15 sensor pipeline (Plan 38-03).

Locks the scheduler.py public contract:
  - SENSOR_POLL_JOB_ID, SENSOR_RETENTION_JOB_ID, SYNC_JOB_ID constants
  - reschedule_sensor_poll helper callable
  - lifespan registers sensor_poll job with (max_instances=1, coalesce=True,
    misfire_grace_time=30)
  - lifespan registers the daily retention cleanup job with a CronTrigger
  - app.state.snmp_engine populated on startup, cleaned up on shutdown
  - Existing Personio sync job id string unchanged (regression guard)

These tests enter the lifespan context directly (no HTTP server spun up).
They require the AppSettings singleton row (seeded by Alembic in migration
`v1_09_app_settings_singleton`); pytest-asyncio + asyncio_mode=auto is
configured in `backend/pytest.ini`.
"""
from __future__ import annotations

import inspect

import pytest
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

from app import scheduler as scheduler_module
from app.scheduler import (
    SENSOR_POLL_JOB_ID,
    SENSOR_RETENTION_JOB_ID,
    SYNC_JOB_ID,
    lifespan,
    reschedule_sensor_poll,
)
from app.scheduler import scheduler as app_scheduler


def test_module_exports_expected_api():
    """The scheduler module exposes the constants + helpers 38-03 locks in."""
    assert SENSOR_POLL_JOB_ID == "sensor_poll"
    assert SENSOR_RETENTION_JOB_ID == "sensor_retention_cleanup"
    # Regression guard: the Personio sync id must not rename.
    assert SYNC_JOB_ID == "personio_sync"
    assert callable(reschedule_sensor_poll)


async def test_sensor_poll_job_registered_on_startup():
    """With AppSettings.sensor_poll_interval_s>0 (default 60), the job registers."""
    app = FastAPI()
    async with lifespan(app):
        job = app_scheduler.get_job(SENSOR_POLL_JOB_ID)
        assert job is not None, "sensor_poll job not registered at lifespan startup"
        assert isinstance(job.trigger, IntervalTrigger), (
            f"sensor_poll job trigger must be IntervalTrigger, got {type(job.trigger)}"
        )


async def test_sensor_poll_job_options():
    """SEN-SCH-02 / PITFALLS C-4: max_instances=1, coalesce=True, misfire_grace_time=30."""
    app = FastAPI()
    async with lifespan(app):
        job = app_scheduler.get_job(SENSOR_POLL_JOB_ID)
        assert job is not None
        assert job.max_instances == 1, (
            f"sensor_poll max_instances must be 1 (got {job.max_instances})"
        )
        assert job.coalesce is True, (
            f"sensor_poll coalesce must be True (got {job.coalesce})"
        )
        assert job.misfire_grace_time == 30, (
            f"sensor_poll misfire_grace_time must be 30 (got {job.misfire_grace_time})"
        )


async def test_retention_cleanup_job_registered():
    """SEN-SCH-06: daily CronTrigger retention job is registered."""
    app = FastAPI()
    async with lifespan(app):
        job = app_scheduler.get_job(SENSOR_RETENTION_JOB_ID)
        assert job is not None, "sensor_retention_cleanup job not registered"
        assert isinstance(job.trigger, CronTrigger), (
            f"retention job trigger must be CronTrigger, got {type(job.trigger)}"
        )


async def test_snmp_engine_populated_on_app_state():
    """PITFALLS C-1 + SEN-BE-03: shared SnmpEngine on app.state + module-level ref."""
    app = FastAPI()
    async with lifespan(app):
        engine = getattr(app.state, "snmp_engine", None)
        assert engine is not None, "app.state.snmp_engine must be populated in lifespan"
        # Module-level ref is the scheduler job's access path (C-1).
        assert scheduler_module._engine is not None
        # Both references must point to the same object (single-instance invariant).
        assert scheduler_module._engine is engine
    # Post-shutdown cleanup
    assert getattr(app.state, "snmp_engine", None) is None
    assert scheduler_module._engine is None


def test_reschedule_helper_signature():
    """SEN-SCH-04: reschedule_sensor_poll(new_interval_s: int) is the Phase 40 hook."""
    sig = inspect.signature(reschedule_sensor_poll)
    params = list(sig.parameters.values())
    assert len(params) == 1, (
        f"reschedule_sensor_poll must take exactly one arg, got {len(params)}"
    )
    # Annotation may be the type object or its string form (depending on from __future__).
    assert params[0].annotation in (int, "int"), (
        f"reschedule_sensor_poll arg annotation must be int, got {params[0].annotation!r}"
    )


def test_personio_job_unchanged():
    """Regression guard — the existing Personio sync id must not be renamed."""
    assert SYNC_JOB_ID == "personio_sync"


async def test_reschedule_sensor_poll_mutates_interval():
    """reschedule_sensor_poll re-pins the sensor_poll interval to a new value."""
    app = FastAPI()
    async with lifespan(app):
        # Pre-state: the job is registered by lifespan at default 60s.
        job_before = app_scheduler.get_job(SENSOR_POLL_JOB_ID)
        assert job_before is not None
        before_interval = job_before.trigger.interval.total_seconds()

        new_interval = 120 if before_interval != 120 else 90
        reschedule_sensor_poll(new_interval)

        job_after = app_scheduler.get_job(SENSOR_POLL_JOB_ID)
        assert job_after is not None, (
            "sensor_poll must still exist after reschedule_sensor_poll(new_interval)"
        )
        assert job_after.trigger.interval.total_seconds() == new_interval

        # reschedule_sensor_poll(0) removes the job (Personio D-07 parity)
        reschedule_sensor_poll(0)
        assert app_scheduler.get_job(SENSOR_POLL_JOB_ID) is None, (
            "reschedule_sensor_poll(0) must remove the job (Personio D-07 parity)"
        )
