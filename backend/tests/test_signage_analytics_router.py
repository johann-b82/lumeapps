"""Phase 53 SGN-ANA-01 — integration tests for GET /api/signage/analytics/devices.

Covers the 6 D-20 scenarios:
  1. All-healthy device (1440 heartbeats) → 100 %, 0 missed, 1440 min
  2. Half-uptime (720 heartbeats every 2 min) → 50 %, 720 missed, 1440 min
  3. Fresh device (30 heartbeats in last 30 min) → 100 % over 30-min denominator
  4. Zero-heartbeat device → uptime_24h_pct null, missed 0, window 0 (D-16)
  5. Revoked device excluded from response (D-07)
  6. Same-minute duplicates counted once (distinct-minute SQL)
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest
import pytest_asyncio

from tests.test_directus_auth import _mint, ADMIN_UUID


ANALYTICS_URL = "/api/signage/analytics/devices"


def _pg_dsn() -> str | None:
    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    db = os.environ.get("POSTGRES_DB")
    host_env = os.environ.get("POSTGRES_HOST")
    host = host_env if (host_env and host_env != "localhost") else "db"
    port = os.environ.get("POSTGRES_PORT", "5432")
    if not (user and password and db):
        return None
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def _require_db() -> str:
    dsn = _pg_dsn()
    if dsn is None:
        pytest.skip("POSTGRES_* not set — analytics router tests need a live DB")
    try:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await conn.execute("SELECT 1")
        finally:
            await conn.close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Postgres not reachable ({dsn}): {exc!s}")
    return dsn


async def _cleanup(dsn: str) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute("DELETE FROM signage_heartbeat_event")
        await conn.execute("DELETE FROM signage_device_tag_map")
        await conn.execute("DELETE FROM signage_devices")
    finally:
        await conn.close()


async def _insert_device(dsn: str, *, revoked: bool = False) -> uuid.UUID:
    device_id = uuid.uuid4()
    revoked_at = datetime.now(timezone.utc) if revoked else None
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_devices (id, name, status, revoked_at)"
            " VALUES ($1, $2, 'online', $3)",
            device_id,
            f"pi-{device_id.hex[:6]}",
            revoked_at,
        )
    finally:
        await conn.close()
    return device_id


async def _insert_heartbeat_batch(
    dsn: str, device_id: uuid.UUID, timestamps: list[datetime]
) -> None:
    """Bulk-insert many heartbeat events in a single connection."""
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.executemany(
            "INSERT INTO signage_heartbeat_event (device_id, ts) "
            "VALUES ($1, $2) ON CONFLICT DO NOTHING",
            [(device_id, ts) for ts in timestamps],
        )
    finally:
        await conn.close()


def _row_for(body: list[dict], device_id: uuid.UUID) -> dict | None:
    return next((r for r in body if r["device_id"] == str(device_id)), None)


@pytest_asyncio.fixture
async def dsn():
    d = await _require_db()
    await _cleanup(d)
    try:
        from app.database import engine

        await engine.dispose()
    except Exception:
        pass
    yield d
    await _cleanup(d)


@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {_mint(ADMIN_UUID)}"}


# ---------- D-20.1 ----------


async def test_analytics_all_healthy_device_returns_100pct(
    client, dsn, admin_headers
):
    device_id = await _insert_device(dsn)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    timestamps = [
        now - timedelta(minutes=i, seconds=1) for i in range(1440)
    ]
    await _insert_heartbeat_batch(dsn, device_id, timestamps)

    resp = await client.get(ANALYTICS_URL, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    row = _row_for(resp.json(), device_id)
    assert row is not None
    assert row["uptime_24h_pct"] == 100.0
    assert row["missed_windows_24h"] == 0
    assert row["window_minutes"] == 1440


# ---------- D-20.2 ----------


async def test_analytics_half_uptime_720_heartbeats(client, dsn, admin_headers):
    device_id = await _insert_device(dsn)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    # 720 distinct minute buckets spread every 2 min across the last ~24 h.
    # Oldest row is at (2*719 + 1) = 1439 s...~24 h ago — denom will be 1440
    # once CEIL kicks in for realistic elapsed wall-clock, but we tolerate
    # [1438..1440] to absorb clock drift between python-side `now` and the
    # Postgres-side `now()` used inside the SQL.
    timestamps = [
        now - timedelta(minutes=i * 2, seconds=1) for i in range(720)
    ]
    await _insert_heartbeat_batch(dsn, device_id, timestamps)

    resp = await client.get(ANALYTICS_URL, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    row = _row_for(resp.json(), device_id)
    assert row is not None
    assert row["window_minutes"] in range(1438, 1441)
    # uptime = 720 / window_minutes. For window_minutes in {1439,1440}, that's
    # 50.0% or 50.03% → rounds to 50.0.
    assert row["uptime_24h_pct"] in (50.0, 50.1)
    # missed = window_minutes - 720
    assert row["missed_windows_24h"] == row["window_minutes"] - 720


# ---------- D-20.3 ----------


async def test_analytics_partial_history_fresh_device_30_minutes(
    client, dsn, admin_headers
):
    device_id = await _insert_device(dsn)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    timestamps = [
        now - timedelta(minutes=i, seconds=1) for i in range(30)
    ]
    await _insert_heartbeat_batch(dsn, device_id, timestamps)

    resp = await client.get(ANALYTICS_URL, headers=admin_headers)
    row = _row_for(resp.json(), device_id)
    assert row is not None
    # Tolerate 29..31 due to minute-boundary rounding (CEIL on first_hb_age_min).
    assert row["window_minutes"] in range(29, 32)
    assert row["uptime_24h_pct"] == 100.0
    assert row["missed_windows_24h"] == 0


# ---------- D-20.4 ----------


async def test_analytics_zero_heartbeat_device_null_state(
    client, dsn, admin_headers
):
    device_id = await _insert_device(dsn)  # no heartbeats
    resp = await client.get(ANALYTICS_URL, headers=admin_headers)
    row = _row_for(resp.json(), device_id)
    # D-16 — either omitted or neutral state; this implementation INCLUDES
    # the device with null uptime_24h_pct.
    assert row is not None
    assert row["uptime_24h_pct"] is None
    assert row["missed_windows_24h"] == 0
    assert row["window_minutes"] == 0


# ---------- D-20.5 ----------


async def test_analytics_revoked_device_excluded(client, dsn, admin_headers):
    device_id = await _insert_device(dsn, revoked=True)
    now = datetime.now(timezone.utc)
    timestamps = [
        now - timedelta(minutes=i, seconds=1) for i in range(100)
    ]
    await _insert_heartbeat_batch(dsn, device_id, timestamps)

    resp = await client.get(ANALYTICS_URL, headers=admin_headers)
    body = resp.json()
    assert all(r["device_id"] != str(device_id) for r in body)


# ---------- D-20.6 ----------


async def test_analytics_same_minute_duplicates_counted_once(
    client, dsn, admin_headers
):
    device_id = await _insert_device(dsn)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    timestamps: list[datetime] = [
        now - timedelta(minutes=i, seconds=1) for i in range(1438)
    ]
    # Two heartbeats inside the same minute bucket (distinct seconds → no PK
    # collision). COUNT(DISTINCT date_trunc('minute', ts)) collapses them.
    timestamps.append(now - timedelta(minutes=1438, seconds=1))
    timestamps.append(now - timedelta(minutes=1438, seconds=30))
    # One more minute to reach 1440 distinct minutes total.
    timestamps.append(now - timedelta(minutes=1439, seconds=1))

    await _insert_heartbeat_batch(dsn, device_id, timestamps)

    resp = await client.get(ANALYTICS_URL, headers=admin_headers)
    row = _row_for(resp.json(), device_id)
    assert row is not None
    assert row["uptime_24h_pct"] == 100.0

    # Raw row count — both duplicates are physically stored (distinct ts).
    conn = await asyncpg.connect(dsn=dsn)
    try:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM signage_heartbeat_event WHERE device_id = $1",
            device_id,
        )
    finally:
        await conn.close()
    # 1438 normal + 2 dup-minute + 1 extra = 1441 physical rows.
    assert count == 1441
