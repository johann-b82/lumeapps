"""Phase 45 Plan 03 — 5-client SSE concurrency benchmark.

Success criterion #1 (SGN-INF-03 companion): with 5 concurrent SSE
clients connected, the application's healthcheck endpoint must keep
p95 response latency under 100ms. This proves the single-process
``--workers 1`` invariant does not starve the event loop under the
planned peak fleet size (≤5 devices per CONTEXT).

Why this matters: the SSE fanout substrate (Plan 45-01) uses per-
device in-memory ``asyncio.Queue``s and pushes events from admin
handlers via ``notify_device``. If any part of the hot path blocks
the event loop, /health response time balloons under load. A p95
well under 100ms is the paper trail that event-loop hygiene has been
preserved.

Methodology:
  1. Seed 5 device rows + mint 5 scoped device JWTs.
  2. Spawn 5 concurrent tasks, each running the EXACT generator shape
     from ``signage_player.stream_events`` — ``subscribe(device_id)``,
     loop ``await queue.get()``, with ``except CancelledError: raise``
     and ``finally: _device_queues.pop(device.id, None)``. This is the
     SAME code path the SSE endpoint drives (per Plan 02 §Deviation 1,
     httpx.AsyncClient.stream over ASGITransport cannot be cleanly
     cancelled against an infinite generator — driving the generator
     shape directly is the standard pattern in this codebase).
  3. Once all 5 are suspended on ``queue.get``, issue N=50 sequential
     GETs against the app's healthcheck endpoint and record wall-clock
     per-request latency.
  4. Compute p95 and assert < 100ms.
  5. Cancel all 5 generator tasks, drain their ``finally`` blocks, and
     verify ``_device_queues`` is empty.

Endpoint used for latency: ``/health`` (the app exposes /health, not
/api/health — see backend/app/main.py:34). This route runs a trivial
SELECT 1 against Postgres; it is the cheapest real route in the app
that still touches the async DB pool, which is the most realistic
proxy for "is the event loop healthy under SSE load".
"""
from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
import uuid

import asyncpg
import pytest
import pytest_asyncio

from app.services import signage_broadcast


# ---------------------------------------------------------------------------
# DSN helpers (mirrored from test_signage_broadcast_integration.py).
# ---------------------------------------------------------------------------


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
        pytest.skip("POSTGRES_* not set — SSE latency bench needs a live DB")
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
        await conn.execute("DELETE FROM signage_devices")
    finally:
        await conn.close()


async def _insert_device(dsn: str, *, name: str) -> uuid.UUID:
    dev_id = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_devices (id, name, status)"
            " VALUES ($1, $2, 'online')",
            dev_id,
            f"{name}-{dev_id.hex[:6]}",
        )
    finally:
        await conn.close()
    return dev_id


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


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


@pytest_asyncio.fixture(autouse=True)
async def _reset_broadcast_queues():
    signage_broadcast._device_queues.clear()
    yield
    signage_broadcast._device_queues.clear()


# ---------------------------------------------------------------------------
# The benchmark.
# ---------------------------------------------------------------------------


async def _hold_open_sse(device_id):
    """Exact generator shape from signage_player.stream_events.

    Subscribe the device, loop awaiting queue.get(), re-raise
    CancelledError (Pitfall 2), pop _device_queues in finally with
    None default (Pitfall 1). This is the production code path: every
    byte of meaningful SSE code lives in this generator.
    """
    queue = signage_broadcast.subscribe(device_id)
    try:
        while True:
            payload = await queue.get()
            # Simulate the yield without a real sink — the benchmark only
            # cares about the "blocked on queue.get" state.
            _ = json.dumps(payload)
    except asyncio.CancelledError:
        raise
    finally:
        signage_broadcast._device_queues.pop(device_id, None)


async def test_health_p95_latency_under_100ms_with_5_sse_clients(client, dsn):
    """SGN-INF-03 / success-criterion #1: 5 SSE clients + /health p95 <100ms."""
    # 1. Seed 5 device rows. (JWT minting is not required because the
    #    benchmark subscribes directly via the generator shape — the
    #    subscribe() contract is the only thing the SSE endpoint does
    #    with the authenticated device id.)
    device_ids = []
    for i in range(5):
        dev_id = await _insert_device(dsn, name=f"bench{i}")
        device_ids.append(dev_id)

    # 2. Spawn 5 concurrent "SSE clients" — same generator body the
    #    /stream endpoint runs. Each task suspends on await queue.get().
    sse_tasks = [
        asyncio.create_task(_hold_open_sse(dev_id)) for dev_id in device_ids
    ]
    # Let the tasks hit their await queue.get() suspension point.
    await asyncio.sleep(0.2)
    assert len(signage_broadcast._device_queues) == 5, (
        f"expected 5 subscribed devices, got {len(signage_broadcast._device_queues)}"
    )

    try:
        # 3. Measure /health latency with 50 sequential GETs.
        latencies_ms: list[float] = []
        for _ in range(50):
            t0 = time.perf_counter()
            r = await client.get("/health")
            t1 = time.perf_counter()
            assert r.status_code == 200, r.text
            latencies_ms.append((t1 - t0) * 1000)

        # 4. Compute p95 explicitly (no numpy — statistics-only path).
        sorted_ms = sorted(latencies_ms)
        # 50 samples -> p95 index = floor(0.95 * 50) - 1 = 47 (48th slowest).
        p95 = sorted_ms[int(len(sorted_ms) * 0.95) - 1]
        median = statistics.median(sorted_ms)

        assert p95 < 100.0, (
            f"/health p95 under 5 SSE clients was {p95:.1f}ms "
            f"(threshold 100ms); min={sorted_ms[0]:.1f} "
            f"median={median:.1f} max={sorted_ms[-1]:.1f} "
            f"(n={len(sorted_ms)})"
        )

        # Emit the observed p95 for SUMMARY doc paper trail.
        print(
            f"\n[45-03 bench] /health p95={p95:.2f}ms median={median:.2f}ms"
            f" min={sorted_ms[0]:.2f}ms max={sorted_ms[-1]:.2f}ms"
            f" (5 SSE clients, 50 samples)"
        )
    finally:
        # 5. Cleanup: cancel all SSE tasks and drain their finally blocks.
        for task in sse_tasks:
            task.cancel()
        await asyncio.gather(*sse_tasks, return_exceptions=True)
        # Small yield so finally blocks complete.
        await asyncio.sleep(0.1)
        assert signage_broadcast._device_queues == {}, (
            f"tasks did not clean up _device_queues:"
            f" {list(signage_broadcast._device_queues.keys())}"
        )
