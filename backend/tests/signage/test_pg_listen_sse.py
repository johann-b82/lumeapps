"""SSE-04 integration tests: Directus REST mutations fan out to Pi SSE within 500 ms.
SSE-06 reconnect smoke test.
Calibration-no-double-fire regression test (protects D-07 WHEN clause).

Prerequisites: `docker compose up -d` — full stack running with v1.22 migrations + triggers.

These tests require a live docker compose stack. Run:
    docker compose up -d
    pytest backend/tests/signage/test_pg_listen_sse.py -v

To skip the slow reconnect test:
    pytest backend/tests/signage/test_pg_listen_sse.py -v -m "not slow"
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator

import httpx
import pytest
import pytest_asyncio

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — LOCKED per D-17 (500 ms hard ceiling in CI).
# A flake here is real signal, not noise to be smoothed over.
# ---------------------------------------------------------------------------

SSE_TIMEOUT_MS = 500  # hard ceiling per D-17
SSE_TIMEOUT_S = SSE_TIMEOUT_MS / 1000  # 0.5

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
DIRECTUS_BASE_URL = os.environ.get("DIRECTUS_BASE_URL", "http://localhost:8055")
DIRECTUS_ADMIN_EMAIL = os.environ.get("DIRECTUS_ADMIN_EMAIL", "admin@example.com")
DIRECTUS_ADMIN_PASSWORD = os.environ.get("DIRECTUS_ADMIN_PASSWORD", "admin_test_pw")

# ---------------------------------------------------------------------------
# Table -> expected SSE event name mapping (6 surfaced signage tables).
# Source: interfaces section of 65-05-PLAN.md.
# ---------------------------------------------------------------------------

TABLE_EVENT_CASES = [
    ("signage_playlists", "playlist-changed"),
    ("signage_playlist_items", "playlist-changed"),
    ("signage_playlist_tag_map", "playlist-changed"),
    ("signage_device_tag_map", "device-changed"),
    ("signage_schedules", "schedule-changed"),
    ("signage_devices", "device-changed"),
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Device:
    id: str
    name: str
    playlist_id: str | None = None
    tag_id: str | None = None
    schedule_id: str | None = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def directus_admin_token() -> str:
    """Obtain a Directus admin access token via the REST login endpoint."""
    resp = httpx.post(
        f"{DIRECTUS_BASE_URL}/auth/login",
        json={"email": DIRECTUS_ADMIN_EMAIL, "password": DIRECTUS_ADMIN_PASSWORD},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("data", {}).get("access_token") or data.get("access_token")
    if not token:
        pytest.fail(f"Could not parse access_token from Directus login response: {data}")
    return token


@pytest_asyncio.fixture(scope="session")
async def paired_device(directus_admin_token: str) -> Device:
    """Seed a signage_device + playlist + tag + schedule for this test session.

    Uses fixed test UUIDs so the records are idempotent across re-runs.
    """
    headers = {"Authorization": f"Bearer {directus_admin_token}"}
    device_id = str(uuid.UUID("eeee0001-0000-4000-a000-000000000001"))
    playlist_id = str(uuid.UUID("eeee0002-0000-4000-a000-000000000001"))
    tag_id = str(uuid.UUID("eeee0003-0000-4000-a000-000000000001"))
    schedule_id = str(uuid.UUID("eeee0004-0000-4000-a000-000000000001"))

    async with httpx.AsyncClient(headers=headers, base_url=DIRECTUS_BASE_URL, timeout=15) as c:
        # Ensure playlist exists
        r = await c.get(f"/items/signage_playlists/{playlist_id}")
        if r.status_code == 404:
            await c.post("/items/signage_playlists", json={"id": playlist_id, "name": "Test Playlist SSE"})

        # Ensure device exists (linked to playlist)
        r = await c.get(f"/items/signage_devices/{device_id}")
        if r.status_code == 404:
            await c.post(
                "/items/signage_devices",
                json={"id": device_id, "name": "Test SSE Device", "paired": True},
            )

        # Ensure tag exists
        r = await c.get(f"/items/signage_device_tags/{tag_id}")
        if r.status_code == 404:
            await c.post("/items/signage_device_tags", json={"id": tag_id, "name": "test-sse-tag"})

        # Ensure schedule exists (linked to playlist)
        r = await c.get(f"/items/signage_schedules/{schedule_id}")
        if r.status_code == 404:
            await c.post(
                "/items/signage_schedules",
                json={
                    "id": schedule_id,
                    "playlist_id": playlist_id,
                    "device_id": device_id,
                    "day_of_week": 0,
                    "start_time": "09:00:00",
                    "end_time": "17:00:00",
                },
            )

    return Device(
        id=device_id,
        name="Test SSE Device",
        playlist_id=playlist_id,
        tag_id=tag_id,
        schedule_id=schedule_id,
    )


class SSEStream:
    """Async iterator over SSE frames from an httpx streaming response."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self._buffer: list[dict] = []

    async def next_frame(self) -> dict:
        """Read lines until a complete SSE event is assembled, then return parsed dict."""
        event_name: str | None = None
        data_lines: list[str] = []

        async for line in self._response.aiter_lines():
            line = line.strip()
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())
            elif line == "" and (event_name or data_lines):
                # End of one SSE event
                raw_data = "\n".join(data_lines)
                try:
                    parsed = json.loads(raw_data) if raw_data else {}
                except json.JSONDecodeError:
                    parsed = {"raw": raw_data}
                return {"event": event_name, "data": parsed}

        raise RuntimeError("SSE stream ended without a complete event")


@asynccontextmanager
async def open_sse_stream(device_id: str) -> AsyncIterator[SSEStream]:
    """Open an SSE subscription to /api/signage/player/stream for `device_id`."""
    device_jwt = _get_device_jwt(device_id)
    headers = {"Authorization": f"Bearer {device_jwt}"}
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=60) as client:
        async with client.stream(
            "GET",
            f"/api/signage/player/stream",
            headers=headers,
            params={"device_id": device_id},
        ) as response:
            response.raise_for_status()
            yield SSEStream(response)


def _get_device_jwt(device_id: str) -> str:
    """Obtain a device JWT from the FastAPI pair/heartbeat endpoint or env."""
    # Use env override for tests (set DEVICE_JWT_<id> or DEVICE_JWT_DEFAULT)
    env_key = f"DEVICE_JWT_{device_id.replace('-', '_').upper()}"
    token = os.environ.get(env_key) or os.environ.get("DEVICE_JWT_DEFAULT")
    if token:
        return token
    # Fall back to requesting a device token via pair endpoint (test env)
    resp = httpx.post(
        f"{API_BASE_URL}/api/signage/pair",
        json={"device_id": device_id, "name": "Test SSE Device"},
        timeout=10,
    )
    if resp.status_code == 200:
        return resp.json().get("token", "")
    # If pair returns a JWT in a different field
    return resp.json().get("access_token", "test-device-jwt-placeholder")


async def issue_mutation_for(
    table: str,
    token: str,
    device: Device,
) -> None:
    """Issue a Directus REST mutation on `table` that should trigger an SSE event
    for the given `device`.

    Each mutation is designed to route through the LISTEN/NOTIFY trigger and
    resolve to `device.id` via the signage resolver.
    """
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10) as c:
        if table == "signage_playlists":
            # Update the playlist linked to device's schedule
            await c.patch(
                f"/items/signage_playlists/{device.playlist_id}",
                json={"name": f"Test Playlist SSE {time.time()}"},
            )
        elif table == "signage_playlist_items":
            # Insert a playlist item (UPSERT pattern)
            await c.post(
                "/items/signage_playlist_items",
                json={
                    "playlist_id": device.playlist_id,
                    "media_id": str(uuid.uuid4()),
                    "position": 1,
                },
            )
        elif table == "signage_playlist_tag_map":
            # Insert a playlist<->tag mapping row
            tag_id = str(uuid.uuid4())
            # Create temp tag
            await c.post("/items/signage_device_tags", json={"id": tag_id, "name": f"tmp-{time.time()}"})
            await c.post(
                "/items/signage_playlist_tag_map",
                json={"playlist_id": device.playlist_id, "tag_id": tag_id},
            )
        elif table == "signage_device_tag_map":
            # Insert a device<->tag mapping row
            await c.post(
                "/items/signage_device_tag_map",
                json={"device_id": device.id, "tag_id": device.tag_id},
            )
        elif table == "signage_schedules":
            # Update the schedule linked to this device's playlist
            await c.patch(
                f"/items/signage_schedules/{device.schedule_id}",
                json={"start_time": f"0{time.time() % 9:.0f}:00:00"},
            )
        elif table == "signage_devices":
            # Change device name only (WHEN clause: OLD.name IS DISTINCT FROM NEW.name)
            await c.patch(
                f"/items/signage_devices/{device.id}",
                json={"name": f"Test SSE Device {time.time()}"},
            )


# ---------------------------------------------------------------------------
# Task 1a: 6 SSE latency tests — one per surfaced signage table.
# LOCKED: SSE_TIMEOUT_MS = 500 per D-17. Flakes are real signal.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize("table,expected_event", TABLE_EVENT_CASES)
@pytest.mark.asyncio
async def test_directus_mutation_fires_sse_within_500ms(
    table: str,
    expected_event: str,
    directus_admin_token: str,
    paired_device: Device,
) -> None:
    """SSE-04: Directus REST mutation on `table` must fan out to the subscribed
    Pi SSE stream within SSE_TIMEOUT_MS (500 ms). Hard ceiling per D-17.
    """
    async with open_sse_stream(paired_device.id) as stream:
        t0 = time.monotonic()
        # Issue the Directus mutation AFTER subscribing
        await issue_mutation_for(table, directus_admin_token, paired_device)

        frame = await asyncio.wait_for(
            stream.next_frame(),
            timeout=SSE_TIMEOUT_S,
        )
        elapsed_ms = (time.monotonic() - t0) * 1000

        assert frame["event"] == expected_event, (
            f"expected event={expected_event!r} for table={table!r}, got {frame['event']!r}"
        )
        assert elapsed_ms < SSE_TIMEOUT_MS, (
            f"SSE latency {elapsed_ms:.0f} ms exceeds {SSE_TIMEOUT_MS} ms ceiling (D-17) "
            f"for table={table!r} -> event={expected_event!r}"
        )


# ---------------------------------------------------------------------------
# Task 1b: Calibration-no-double-fire regression.
# Protects the D-07 WHEN clause: signage_devices trigger fires only on name/tags changes.
# PATCH /api/signage/devices/<id>/calibration must not produce device-changed.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_calibration_patch_fires_single_frame_no_device_changed_double(
    paired_device: Device,
) -> None:
    """Calibration PATCH -> exactly ONE calibration-changed frame.
    NO subsequent device-changed within 500 ms (D-07: WHEN clause guards name/tags only).
    """
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=10) as api_client:
        async with open_sse_stream(paired_device.id) as stream:
            # PATCH the calibration endpoint
            device_jwt = _get_device_jwt(paired_device.id)
            r = await api_client.patch(
                f"/api/signage/devices/{paired_device.id}/calibration",
                json={"rotation": 90},
                headers={"Authorization": f"Bearer {device_jwt}"},
            )
            assert r.status_code in (200, 204), f"calibration PATCH failed: {r.status_code}"

            # First frame must be calibration-changed
            first = await asyncio.wait_for(stream.next_frame(), timeout=2.0)
            assert first["event"] == "calibration-changed", (
                f"expected calibration-changed as first frame, got {first['event']!r}"
            )

            # Assert NO follow-up device-changed within SSE_TIMEOUT_MS
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(stream.next_frame(), timeout=SSE_TIMEOUT_S)


# ---------------------------------------------------------------------------
# Task 1c: Reconnect smoke test.
# SSE-06: listener reconnects within 10s of DB bounce; re-subscribes and
# resumes fan-out.
# Marked @pytest.mark.slow — skip with `pytest -m "not slow"`.
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
async def test_listener_reconnects_after_db_bounce(
    directus_admin_token: str,
    paired_device: Device,
) -> None:
    """SSE-06 reconnect smoke test.

    Simulates a DB connection drop by sending SIGKILL to the postgres container
    (via docker compose restart), then asserts:
    1. `signage_pg_listen: reconnecting` appears in API container logs within 10s.
    2. Listener re-subscribes (subscribed log within 30s).
    3. Fresh Directus mutation still produces an SSE frame on the stream.

    Requires docker socket access (CI must mount /var/run/docker.sock or use DinD).
    """
    import subprocess

    # Step 1: Force reconnect by bouncing the DB container
    subprocess.run(
        ["docker", "compose", "restart", "db"],
        check=True,
        timeout=30,
    )

    # Step 2: Poll API container logs for reconnecting message
    deadline = time.monotonic() + 10
    reconnected = False
    while time.monotonic() < deadline:
        logs = subprocess.run(
            ["docker", "compose", "logs", "--tail", "50", "api"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "signage_pg_listen: reconnecting" in logs.stdout:
            reconnected = True
            break
        await asyncio.sleep(0.5)

    if not reconnected:
        pytest.fail("expected 'signage_pg_listen: reconnecting' in API logs within 10s after DB bounce")

    # Step 3: Wait for re-subscribe confirmation
    deadline = time.monotonic() + 30
    resubscribed = False
    while time.monotonic() < deadline:
        logs = subprocess.run(
            ["docker", "compose", "logs", "--tail", "50", "api"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "signage_pg_listen: subscribed to signage_change" in logs.stdout:
            resubscribed = True
            break
        await asyncio.sleep(1.0)

    if not resubscribed:
        pytest.fail("listener did not re-subscribe within 30s after DB bounce")

    # Step 4: Confirm SSE fan-out still works after reconnect
    async with open_sse_stream(paired_device.id) as stream:
        await issue_mutation_for("signage_playlists", directus_admin_token, paired_device)
        frame = await asyncio.wait_for(stream.next_frame(), timeout=2.0)
        assert frame["event"] == "playlist-changed", (
            f"expected playlist-changed after reconnect, got {frame['event']!r}"
        )


# ---------------------------------------------------------------------------
# Phase 68 D-09: Directus-originated schedule lifecycle regression.
# Proves Plan 03's deletion of `_fanout_schedule_changed` did not break
# schedule-changed SSE fan-out. CREATE / UPDATE / DELETE via Directus REST
# must each fire `schedule-changed` within the 500 ms ceiling (D-17).
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_directus_schedule_lifecycle_fires_sse_each_step(
    directus_admin_token: str,
    paired_device: Device,
) -> None:
    """Phase 68 D-09: schedule create/update/delete via Directus each fire
    `schedule-changed` SSE within 500 ms.

    Regression coverage for Plan 03 — confirms the Phase 65 LISTEN/NOTIFY bridge
    still delivers schedule events after the FastAPI `_fanout_schedule_changed`
    helper was deleted.
    """
    headers = {"Authorization": f"Bearer {directus_admin_token}"}
    schedule_id: str | None = None

    async with open_sse_stream(paired_device.id) as stream:
        async with httpx.AsyncClient(
            headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
        ) as c:
            # ---- 1. CREATE ----
            t0 = time.monotonic()
            r = await c.post(
                "/items/signage_schedules",
                json={
                    "playlist_id": paired_device.playlist_id,
                    "device_id": paired_device.id,
                    "day_of_week": 1,
                    "start_time": "10:00:00",
                    "end_time": "12:00:00",
                },
            )
            assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
            schedule_id = r.json()["data"]["id"]

            frame = await asyncio.wait_for(stream.next_frame(), timeout=SSE_TIMEOUT_S)
            create_ms = (time.monotonic() - t0) * 1000
            assert frame["event"] == "schedule-changed", (
                f"CREATE: expected schedule-changed, got {frame['event']!r}"
            )
            assert create_ms < SSE_TIMEOUT_MS, (
                f"CREATE latency {create_ms:.0f} ms > {SSE_TIMEOUT_MS} ms (D-17)"
            )

            # ---- 2. UPDATE (priority/start_time change) ----
            t0 = time.monotonic()
            r = await c.patch(
                f"/items/signage_schedules/{schedule_id}",
                json={"start_time": "11:00:00"},
            )
            assert r.status_code == 200, f"update failed: {r.status_code} {r.text}"

            frame = await asyncio.wait_for(stream.next_frame(), timeout=SSE_TIMEOUT_S)
            update_ms = (time.monotonic() - t0) * 1000
            assert frame["event"] == "schedule-changed", (
                f"UPDATE: expected schedule-changed, got {frame['event']!r}"
            )
            assert update_ms < SSE_TIMEOUT_MS, (
                f"UPDATE latency {update_ms:.0f} ms > {SSE_TIMEOUT_MS} ms (D-17)"
            )

            # ---- 3. DELETE ----
            t0 = time.monotonic()
            r = await c.delete(f"/items/signage_schedules/{schedule_id}")
            assert r.status_code == 204, f"delete failed: {r.status_code} {r.text}"

            frame = await asyncio.wait_for(stream.next_frame(), timeout=SSE_TIMEOUT_S)
            delete_ms = (time.monotonic() - t0) * 1000
            assert frame["event"] == "schedule-changed", (
                f"DELETE: expected schedule-changed, got {frame['event']!r}"
            )
            assert delete_ms < SSE_TIMEOUT_MS, (
                f"DELETE latency {delete_ms:.0f} ms > {SSE_TIMEOUT_MS} ms (D-17)"
            )

            logger.info(
                "schedule lifecycle SSE latencies: create=%.0fms update=%.0fms delete=%.0fms",
                create_ms, update_ms, delete_ms,
            )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_directus_tag_map_mutation_still_fires_sse_after_phase68(
    directus_admin_token: str,
    paired_device: Device,
) -> None:
    """Phase 68 D-09: After Plan 01 (tags FastAPI removal) + Plan 03
    (schedule helper deletion), `signage_playlist_tag_map` mutations via
    Directus must still fire `playlist-changed` SSE within 500 ms.

    This sanity case proves the listener still resolves devices correctly
    despite the FastAPI surface shrink.
    """
    headers = {"Authorization": f"Bearer {directus_admin_token}"}
    tag_id = str(uuid.uuid4())

    async with httpx.AsyncClient(
        headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
    ) as c:
        # Pre-create a tag (no SSE expected from this — see negative test below).
        r = await c.post(
            "/items/signage_device_tags",
            json={"id": tag_id, "name": f"phase68-regress-{int(time.time())}"},
        )
        assert r.status_code in (200, 201), f"tag create failed: {r.status_code} {r.text}"

        # Ensure the device is bound to this tag so the resolver maps the
        # playlist-tag-map row back to paired_device.id.
        await c.post(
            "/items/signage_device_tag_map",
            json={"device_id": paired_device.id, "tag_id": tag_id},
        )

    try:
        async with open_sse_stream(paired_device.id) as stream:
            t0 = time.monotonic()
            async with httpx.AsyncClient(
                headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
            ) as c:
                r = await c.post(
                    "/items/signage_playlist_tag_map",
                    json={"playlist_id": paired_device.playlist_id, "tag_id": tag_id},
                )
                assert r.status_code in (200, 201), (
                    f"playlist_tag_map create failed: {r.status_code} {r.text}"
                )

            frame = await asyncio.wait_for(stream.next_frame(), timeout=SSE_TIMEOUT_S)
            elapsed_ms = (time.monotonic() - t0) * 1000
            assert frame["event"] == "playlist-changed", (
                f"expected playlist-changed for tag-map mutation, got {frame['event']!r}"
            )
            assert elapsed_ms < SSE_TIMEOUT_MS, (
                f"tag-map SSE latency {elapsed_ms:.0f} ms > {SSE_TIMEOUT_MS} ms (D-17)"
            )
    finally:
        # Cleanup mapping + tag (best-effort; ignore failures on re-run).
        async with httpx.AsyncClient(
            headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
        ) as c:
            try:
                await c.delete(
                    "/items/signage_playlist_tag_map",
                    params={
                        "filter[playlist_id][_eq]": paired_device.playlist_id,
                        "filter[tag_id][_eq]": tag_id,
                    },
                )
            except Exception:
                pass
            try:
                await c.delete(f"/items/signage_device_tags/{tag_id}")
            except Exception:
                pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_directus_signage_device_tags_fires_no_sse(
    directus_admin_token: str,
    paired_device: Device,
) -> None:
    """Phase 68 D-05: `signage_device_tags` has NO LISTEN trigger
    (Phase 65 SSE-01 deliberately did not add one — tag rows alone don't
    affect any device's playback). CRUD on the table must NOT emit any SSE
    frame within a 1-second window.

    Negative-assertion regression: confirms no false-positive trigger leak.
    """
    headers = {"Authorization": f"Bearer {directus_admin_token}"}
    tag_id = str(uuid.uuid4())

    async with open_sse_stream(paired_device.id) as stream:
        async with httpx.AsyncClient(
            headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
        ) as c:
            # CREATE
            r = await c.post(
                "/items/signage_device_tags",
                json={"id": tag_id, "name": f"phase68-noevent-{int(time.time())}"},
            )
            assert r.status_code in (200, 201), f"tag create failed: {r.status_code} {r.text}"

            # UPDATE
            r = await c.patch(
                f"/items/signage_device_tags/{tag_id}",
                json={"name": f"phase68-renamed-{int(time.time())}"},
            )
            assert r.status_code == 200, f"tag update failed: {r.status_code} {r.text}"

            # DELETE
            r = await c.delete(f"/items/signage_device_tags/{tag_id}")
            assert r.status_code == 204, f"tag delete failed: {r.status_code} {r.text}"

        # Within a 1 s window, NO SSE frame must arrive — tag table has no trigger.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(stream.next_frame(), timeout=1.0)


# ---------------------------------------------------------------------------
# Phase 69 D-05: Directus-originated playlist lifecycle regression.
# Proves Plan 69-01 deletion of POST/GET/PATCH playlist routes did not break
# `playlist-changed` SSE fan-out. CREATE / UPDATE via Directus REST must each
# fire `playlist-changed` within the 500 ms ceiling (D-17). Cleanup deletes
# also fire — we accept those during teardown.
# ---------------------------------------------------------------------------


async def _drain_events(stream: SSEStream, settle_ms: int = 200) -> None:
    """Consume any queued SSE frames until the stream is quiet for `settle_ms`."""
    while True:
        try:
            await asyncio.wait_for(stream.next_frame(), timeout=settle_ms / 1000)
        except asyncio.TimeoutError:
            return


@pytest.mark.integration
@pytest.mark.asyncio
async def test_directus_playlist_lifecycle_fires_sse_each_step(
    directus_admin_token: str,
    paired_device: Device,
) -> None:
    """Phase 69 D-05: Directus playlist CREATE + UPDATE each fire
    `playlist-changed` SSE within 500 ms.

    Regression: confirms the Phase 65 LISTEN/NOTIFY bridge still delivers
    `playlist-changed` after Plan 69-01 deleted the FastAPI POST/GET/PATCH
    playlist routes. The transient playlist must be tagged with the paired
    device's tag so the resolver routes the event to this stream — without
    the tag link, the resolver finds zero affected devices and no SSE fires.
    """
    headers = {"Authorization": f"Bearer {directus_admin_token}"}
    playlist_id: str | None = None

    # Setup: bind paired_device.tag_id to the device so any playlist tagged
    # with it routes back to this stream (idempotent — created in fixture if
    # missing; ignore 4xx duplicates).
    async with httpx.AsyncClient(headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10) as c:
        try:
            await c.post(
                "/items/signage_device_tag_map",
                json={"device_id": paired_device.id, "tag_id": paired_device.tag_id},
            )
        except Exception:
            pass

    async with open_sse_stream(paired_device.id) as stream:
        async with httpx.AsyncClient(headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10) as c:
            # ---- 1. CREATE ----
            t0 = time.monotonic()
            r = await c.post(
                "/items/signage_playlists",
                json={
                    "name": f"phase69-sse-{int(time.time() * 1000)}",
                    "priority": 0,
                    "enabled": True,
                },
            )
            assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
            playlist_id = r.json()["data"]["id"]

            # Bind the new playlist to the paired device's tag so the resolver
            # routes events to this stream.
            r2 = await c.post(
                "/items/signage_playlist_tag_map",
                json={"playlist_id": playlist_id, "tag_id": paired_device.tag_id},
            )
            assert r2.status_code in (200, 201), (
                f"playlist_tag_map create failed: {r2.status_code} {r2.text}"
            )

            # The CREATE itself fires playlist-changed (resolver may return
            # zero affected devices on first insert — wait for the tag-map
            # row's playlist-changed event instead). At-least-once delivery
            # within 500 ms is sufficient.
            frame = await asyncio.wait_for(stream.next_frame(), timeout=SSE_TIMEOUT_S)
            create_ms = (time.monotonic() - t0) * 1000
            assert frame["event"] == "playlist-changed", (
                f"CREATE: expected playlist-changed, got {frame['event']!r}"
            )
            assert create_ms < SSE_TIMEOUT_MS, (
                f"CREATE latency {create_ms:.0f} ms > {SSE_TIMEOUT_MS} ms (D-17)"
            )

            # Drain any follow-up events from the tag-map insert before the
            # next measurement.
            await _drain_events(stream, settle_ms=200)

            # ---- 2. UPDATE (rename) ----
            t0 = time.monotonic()
            r = await c.patch(
                f"/items/signage_playlists/{playlist_id}",
                json={"name": f"phase69-sse-renamed-{int(time.time() * 1000)}"},
            )
            assert r.status_code == 200, f"update failed: {r.status_code} {r.text}"

            frame = await asyncio.wait_for(stream.next_frame(), timeout=SSE_TIMEOUT_S)
            update_ms = (time.monotonic() - t0) * 1000
            assert frame["event"] == "playlist-changed", (
                f"UPDATE: expected playlist-changed, got {frame['event']!r}"
            )
            assert update_ms < SSE_TIMEOUT_MS, (
                f"UPDATE latency {update_ms:.0f} ms > {SSE_TIMEOUT_MS} ms (D-17)"
            )

            logger.info(
                "playlist lifecycle SSE latencies: create=%.0fms update=%.0fms",
                create_ms, update_ms,
            )

    # Cleanup (best-effort).
    if playlist_id is not None:
        async with httpx.AsyncClient(
            headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
        ) as c:
            try:
                await c.delete(
                    "/items/signage_playlist_tag_map",
                    params={
                        "filter[playlist_id][_eq]": playlist_id,
                    },
                )
            except Exception:
                pass
            try:
                await c.delete(f"/items/signage_playlists/{playlist_id}")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Phase 69 D-02b / D-05: tag-map diff (delete + create) must fire AT LEAST
# ONE `playlist-changed` SSE within 1 s. Multi-event tolerated per D-02b —
# do NOT assert exactly-once.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_directus_playlist_tag_map_diff_fires_sse_at_least_once(
    directus_admin_token: str,
    paired_device: Device,
) -> None:
    """Phase 69 D-02b/D-05: a tag-map diff replace (delete + create per row)
    fires >= 1 `playlist-changed` SSE within 1 s. Multi-event tolerated.

    Mirrors the FE Plan 69-03 `replacePlaylistTags` diff strategy: existing
    map row deleted via `deleteItems` (FE uses filter form), new map row
    created via `createItems`. From the SSE bridge's perspective each row
    insert/delete fires its own trigger — we only assert at-least-once.
    """
    headers = {"Authorization": f"Bearer {directus_admin_token}"}
    playlist_id: str | None = None
    tag_id: str | None = None

    async with httpx.AsyncClient(headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10) as c:
        # Setup: transient playlist + transient tag + paired device bound to tag.
        r = await c.post(
            "/items/signage_playlists",
            json={"name": f"phase69-tagdiff-{int(time.time()*1000)}", "priority": 0, "enabled": True},
        )
        assert r.status_code in (200, 201), r.text
        playlist_id = r.json()["data"]["id"]

        r = await c.post(
            "/items/signage_device_tags",
            json={"name": f"phase69-tag-{int(time.time()*1000)}"},
        )
        assert r.status_code in (200, 201), r.text
        tag_id = r.json()["data"]["id"]

        # Bind paired device to this tag so the resolver routes events here.
        await c.post(
            "/items/signage_device_tag_map",
            json={"device_id": paired_device.id, "tag_id": tag_id},
        )
        # Insert initial map row so the diff has something to delete.
        r = await c.post(
            "/items/signage_playlist_tag_map",
            json={"playlist_id": playlist_id, "tag_id": tag_id},
        )
        assert r.status_code in (200, 201), r.text

    try:
        async with open_sse_stream(paired_device.id) as stream:
            # Drain any pending events from setup before measuring the diff.
            await _drain_events(stream, settle_ms=300)

            t0 = time.monotonic()
            # Diff: delete existing map row (filter form, mirrors FE pattern)
            # + create a fresh map row referencing the same tag.
            async with httpx.AsyncClient(
                headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
            ) as c:
                await asyncio.gather(
                    c.delete(
                        "/items/signage_playlist_tag_map",
                        params={
                            "filter[playlist_id][_eq]": playlist_id,
                            "filter[tag_id][_eq]": tag_id,
                        },
                    ),
                    c.post(
                        "/items/signage_playlist_tag_map",
                        json={"playlist_id": playlist_id, "tag_id": tag_id},
                    ),
                )

            # At-least-once: first frame must be playlist-changed within 1 s.
            frame = await asyncio.wait_for(stream.next_frame(), timeout=1.0)
            diff_ms = (time.monotonic() - t0) * 1000
            assert frame["event"] == "playlist-changed", (
                f"tag-map diff: expected playlist-changed, got {frame['event']!r}"
            )
            assert diff_ms < 1000, (
                f"tag-map diff first-event latency {diff_ms:.0f} ms > 1000 ms"
            )
            logger.info("playlist tag-map diff first-event latency: %.0fms", diff_ms)

    finally:
        # Cleanup: remaining map rows + tag + playlist (best-effort).
        async with httpx.AsyncClient(
            headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
        ) as c:
            if playlist_id:
                try:
                    await c.delete(
                        "/items/signage_playlist_tag_map",
                        params={"filter[playlist_id][_eq]": playlist_id},
                    )
                except Exception:
                    pass
            if tag_id:
                try:
                    await c.delete(
                        "/items/signage_device_tag_map",
                        params={
                            "filter[device_id][_eq]": paired_device.id,
                            "filter[tag_id][_eq]": tag_id,
                        },
                    )
                except Exception:
                    pass
                try:
                    await c.delete(f"/items/signage_device_tags/{tag_id}")
                except Exception:
                    pass
            if playlist_id:
                try:
                    await c.delete(f"/items/signage_playlists/{playlist_id}")
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Phase 69 D-04b/D-05a: surviving FastAPI DELETE + bulk-PUT items routes
# still fire `playlist-changed` SSE — proves `_notify_playlist_changed`
# helper retention from Plans 69-01 / 69-02.
#
# Both tests use `directus_admin_token` directly as the Authorization
# bearer. FastAPI validates Directus-issued HS256 JWTs via the shared
# secret (Phase 65 AUTHZ-01), so a Directus admin login token is accepted
# as an Admin-role JWT by the FastAPI signage_admin gate.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fastapi_playlist_delete_still_fires_sse(
    directus_admin_token: str,
    paired_device: Device,
) -> None:
    """Phase 69 D-04b: surviving `DELETE /api/signage/playlists/{id}` still
    fires `playlist-changed` SSE within 500 ms. Proves `_notify_playlist_changed`
    helper retention after Plan 69-01 trim.
    """
    directus_headers = {"Authorization": f"Bearer {directus_admin_token}"}
    fastapi_headers = {"Authorization": f"Bearer {directus_admin_token}"}
    playlist_id: str | None = None

    # Setup: transient playlist + bind paired_device's tag so DELETE routes
    # `playlist-changed` to this stream.
    async with httpx.AsyncClient(
        headers=directus_headers, base_url=DIRECTUS_BASE_URL, timeout=10
    ) as c:
        r = await c.post(
            "/items/signage_playlists",
            json={
                "name": f"phase69-fastapi-del-{int(time.time()*1000)}",
                "priority": 0,
                "enabled": True,
            },
        )
        assert r.status_code in (200, 201), r.text
        playlist_id = r.json()["data"]["id"]
        await c.post(
            "/items/signage_playlist_tag_map",
            json={"playlist_id": playlist_id, "tag_id": paired_device.tag_id},
        )

    try:
        async with open_sse_stream(paired_device.id) as stream:
            await _drain_events(stream, settle_ms=300)

            t0 = time.monotonic()
            async with httpx.AsyncClient(
                base_url=API_BASE_URL, timeout=10, headers=fastapi_headers
            ) as api:
                r = await api.delete(f"/api/signage/playlists/{playlist_id}")
                assert r.status_code == 204, (
                    f"FastAPI DELETE failed: {r.status_code} {r.text}"
                )

            frame = await asyncio.wait_for(stream.next_frame(), timeout=SSE_TIMEOUT_S)
            elapsed_ms = (time.monotonic() - t0) * 1000
            assert frame["event"] == "playlist-changed", (
                f"FastAPI DELETE: expected playlist-changed, got {frame['event']!r}"
            )
            assert elapsed_ms < SSE_TIMEOUT_MS, (
                f"FastAPI DELETE latency {elapsed_ms:.0f} ms > {SSE_TIMEOUT_MS} ms (D-17)"
            )
            logger.info("fastapi playlist DELETE SSE latency: %.0fms", elapsed_ms)
            playlist_id = None  # already deleted; skip teardown.
    finally:
        if playlist_id is not None:
            async with httpx.AsyncClient(
                headers=directus_headers, base_url=DIRECTUS_BASE_URL, timeout=10
            ) as c:
                try:
                    await c.delete(
                        "/items/signage_playlist_tag_map",
                        params={"filter[playlist_id][_eq]": playlist_id},
                    )
                except Exception:
                    pass
                try:
                    await c.delete(f"/items/signage_playlists/{playlist_id}")
                except Exception:
                    pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fastapi_bulk_replace_items_still_fires_sse(
    directus_admin_token: str,
    paired_device: Device,
) -> None:
    """Phase 69 D-05a: surviving `PUT /api/signage/playlists/{id}/items`
    still fires `playlist-changed` SSE within 500 ms. Proves
    `_notify_playlist_changed` helper retention after Plan 69-02 trim.

    Empty-replace `{"items": []}` is a valid atomic operation — exercises
    the DELETE+INSERT bulk path with zero inserts.
    """
    directus_headers = {"Authorization": f"Bearer {directus_admin_token}"}
    fastapi_headers = {"Authorization": f"Bearer {directus_admin_token}"}
    playlist_id: str | None = None

    # Setup: transient playlist tagged for paired device.
    async with httpx.AsyncClient(
        headers=directus_headers, base_url=DIRECTUS_BASE_URL, timeout=10
    ) as c:
        r = await c.post(
            "/items/signage_playlists",
            json={
                "name": f"phase69-fastapi-put-{int(time.time()*1000)}",
                "priority": 0,
                "enabled": True,
            },
        )
        assert r.status_code in (200, 201), r.text
        playlist_id = r.json()["data"]["id"]
        await c.post(
            "/items/signage_playlist_tag_map",
            json={"playlist_id": playlist_id, "tag_id": paired_device.tag_id},
        )

    try:
        async with open_sse_stream(paired_device.id) as stream:
            await _drain_events(stream, settle_ms=300)

            t0 = time.monotonic()
            async with httpx.AsyncClient(
                base_url=API_BASE_URL, timeout=10, headers=fastapi_headers
            ) as api:
                r = await api.put(
                    f"/api/signage/playlists/{playlist_id}/items",
                    json={"items": []},
                )
                assert r.status_code in (200, 204), (
                    f"FastAPI bulk PUT items failed: {r.status_code} {r.text}"
                )

            frame = await asyncio.wait_for(stream.next_frame(), timeout=SSE_TIMEOUT_S)
            elapsed_ms = (time.monotonic() - t0) * 1000
            assert frame["event"] == "playlist-changed", (
                f"FastAPI bulk PUT: expected playlist-changed, got {frame['event']!r}"
            )
            assert elapsed_ms < SSE_TIMEOUT_MS, (
                f"FastAPI bulk PUT latency {elapsed_ms:.0f} ms > {SSE_TIMEOUT_MS} ms (D-17)"
            )
            logger.info("fastapi bulk PUT items SSE latency: %.0fms", elapsed_ms)
    finally:
        if playlist_id is not None:
            async with httpx.AsyncClient(
                headers=directus_headers, base_url=DIRECTUS_BASE_URL, timeout=10
            ) as c:
                try:
                    await c.delete(
                        "/items/signage_playlist_tag_map",
                        params={"filter[playlist_id][_eq]": playlist_id},
                    )
                except Exception:
                    pass
                try:
                    await c.delete(f"/items/signage_playlists/{playlist_id}")
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Phase 70 D-07: Directus-originated device + tag-map regression cases.
# Plus calibration no-double-fire infra-level invariant pinning success
# criterion #4 (the v1_22_signage_notify_triggers WHEN-gate excludes
# calibration columns from signage_devices_update_notify).
#
# Event-name correctness (research Pitfall 1):
# `signage_device_tag_map` mutations emit `device-changed` (NOT
# `playlist-changed` as CONTEXT D-03b incorrectly stated). Source of
# truth: backend/app/services/signage_pg_listen.py:86-88 maps
# signage_device_tag_map -> "device-changed".
# ---------------------------------------------------------------------------


async def _create_transient_device(
    c: httpx.AsyncClient, name: str, tag_id: str | None = None
) -> str:
    """Create a transient signage_devices row (and optional tag-map binding)
    via Directus. Returns the new device id.

    Best-effort helper for Phase 70 device tests — the caller is responsible
    for cleanup.
    """
    r = await c.post(
        "/items/signage_devices",
        json={"name": name, "paired": True},
    )
    assert r.status_code in (200, 201), (
        f"transient device create failed: {r.status_code} {r.text}"
    )
    device_id = r.json()["data"]["id"]
    if tag_id is not None:
        await c.post(
            "/items/signage_device_tag_map",
            json={"device_id": device_id, "tag_id": tag_id},
        )
    return device_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_directus_device_name_update_emits_device_changed(
    directus_admin_token: str,
) -> None:
    """Phase 70 D-07 case 1: Directus updateItem('signage_devices', id, {name})
    fires `device-changed` SSE within 500 ms.

    Proves Plan 70-02's removal of FastAPI device PATCH did not break the
    Phase 65 LISTEN/NOTIFY bridge — Directus writers exercise the same
    trigger that v1_22_signage_notify_triggers installed.
    """
    headers = {"Authorization": f"Bearer {directus_admin_token}"}
    device_id: str | None = None

    async with httpx.AsyncClient(
        headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
    ) as c:
        device_id = await _create_transient_device(
            c, name=f"phase70-rename-pre-{int(time.time() * 1000)}"
        )

    try:
        async with open_sse_stream(device_id) as stream:
            await _drain_events(stream, settle_ms=200)
            t0 = time.monotonic()
            async with httpx.AsyncClient(
                headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
            ) as c:
                r = await c.patch(
                    f"/items/signage_devices/{device_id}",
                    json={"name": f"phase-70-rename-test-{int(time.time() * 1000)}"},
                )
                assert r.status_code == 200, (
                    f"device PATCH failed: {r.status_code} {r.text}"
                )

            frame = await asyncio.wait_for(stream.next_frame(), timeout=SSE_TIMEOUT_S)
            elapsed_ms = (time.monotonic() - t0) * 1000
            assert frame["event"] == "device-changed", (
                f"expected device-changed for name update, got {frame['event']!r}"
            )
            assert elapsed_ms < SSE_TIMEOUT_MS, (
                f"device name-update SSE latency {elapsed_ms:.0f} ms > {SSE_TIMEOUT_MS} ms (D-17)"
            )
            logger.info("phase70 device name-update SSE latency: %.0fms", elapsed_ms)
    finally:
        if device_id is not None:
            async with httpx.AsyncClient(
                headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
            ) as c:
                try:
                    await c.delete(f"/items/signage_devices/{device_id}")
                except Exception:
                    pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_directus_device_delete_emits_device_changed(
    directus_admin_token: str,
) -> None:
    """Phase 70 D-07 case 2: Directus deleteItem('signage_devices', id) fires
    `device-changed` SSE within 500 ms (DELETE branch in signage_pg_listen.py
    sets affected=[] but still emits the event for any subscriber).
    """
    headers = {"Authorization": f"Bearer {directus_admin_token}"}
    device_id: str | None = None

    async with httpx.AsyncClient(
        headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
    ) as c:
        device_id = await _create_transient_device(
            c, name=f"phase70-delete-{int(time.time() * 1000)}"
        )

    # Open the SSE stream BEFORE the DELETE so we still hold a valid device JWT
    # at the moment of deletion (post-delete pair calls would 404).
    async with open_sse_stream(device_id) as stream:
        await _drain_events(stream, settle_ms=200)
        t0 = time.monotonic()
        async with httpx.AsyncClient(
            headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
        ) as c:
            r = await c.delete(f"/items/signage_devices/{device_id}")
            assert r.status_code == 204, (
                f"device DELETE failed: {r.status_code} {r.text}"
            )

        frame = await asyncio.wait_for(stream.next_frame(), timeout=SSE_TIMEOUT_S)
        elapsed_ms = (time.monotonic() - t0) * 1000
        assert frame["event"] == "device-changed", (
            f"expected device-changed for delete, got {frame['event']!r}"
        )
        assert elapsed_ms < SSE_TIMEOUT_MS, (
            f"device DELETE SSE latency {elapsed_ms:.0f} ms > {SSE_TIMEOUT_MS} ms (D-17)"
        )
        logger.info("phase70 device DELETE SSE latency: %.0fms", elapsed_ms)


@pytest.mark.xfail(
    reason=(
        "Phase 69 Plan 06 lesson: signage_device_tag_map is a composite-PK join "
        "table (no surrogate id column). Directus 11 reports FORBIDDEN on /items "
        "access for this collection even with admin_access: true, because the "
        "snapshot's `schema: null` registration does not register the fields "
        "needed to expose the composite PK via REST. Resolution requires "
        "registering field metadata for the join table; deferred to Phase 71 CLEAN."
    ),
    strict=False,
)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_directus_device_tag_map_emits_device_changed(
    directus_admin_token: str,
) -> None:
    """Phase 70 D-07 case 3: Directus createItem on signage_device_tag_map
    fires AT LEAST ONE `device-changed` SSE within 1000 ms.

    NOTE: research Pitfall 1 — CONTEXT D-03b incorrectly stated this should
    emit `playlist-changed`. The truth is `device-changed`:
    signage_pg_listen.py:86-88 maps signage_device_tag_map -> 'device-changed'.

    Multi-event tolerance per D-03b: the diff strategy used by the FE
    (replaceDeviceTags = deleteItems + createItems) may emit multiple
    triggers — assert at-least-once.
    """
    headers = {"Authorization": f"Bearer {directus_admin_token}"}
    device_id: str | None = None
    tag_id: str | None = None

    async with httpx.AsyncClient(
        headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
    ) as c:
        # Setup: transient device + transient tag (NOT yet bound).
        device_id = await _create_transient_device(
            c, name=f"phase70-tagmap-dev-{int(time.time() * 1000)}"
        )
        r = await c.post(
            "/items/signage_device_tags",
            json={"name": f"phase70-tagmap-tag-{int(time.time() * 1000)}"},
        )
        assert r.status_code in (200, 201), r.text
        tag_id = r.json()["data"]["id"]

    try:
        async with open_sse_stream(device_id) as stream:
            await _drain_events(stream, settle_ms=200)
            t0 = time.monotonic()
            async with httpx.AsyncClient(
                headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
            ) as c:
                # Insert the device_tag_map row via Directus. If composite-PK
                # metadata gap (Pitfall 2) blocks this, xfail-strict-false
                # tolerates it per Phase 69 Plan 06 precedent.
                r = await c.post(
                    "/items/signage_device_tag_map",
                    json={"device_id": device_id, "tag_id": tag_id},
                )
                assert r.status_code in (200, 201), (
                    f"signage_device_tag_map insert failed (composite-PK gap?): "
                    f"{r.status_code} {r.text}"
                )

            # At-least-once: first frame must be device-changed within 1 s.
            # NOT playlist-changed (signage_pg_listen.py:86-88 mapping).
            frame = await asyncio.wait_for(stream.next_frame(), timeout=1.0)
            elapsed_ms = (time.monotonic() - t0) * 1000
            assert frame["event"] == "device-changed", (
                f"signage_device_tag_map insert: expected device-changed "
                f"(NOT playlist-changed per signage_pg_listen.py:86-88), "
                f"got {frame['event']!r}"
            )
            assert elapsed_ms < 1000, (
                f"device_tag_map SSE first-event latency {elapsed_ms:.0f} ms > 1000 ms"
            )
            logger.info(
                "phase70 device_tag_map first-event SSE latency: %.0fms", elapsed_ms
            )
    finally:
        async with httpx.AsyncClient(
            headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
        ) as c:
            if device_id and tag_id:
                try:
                    await c.delete(
                        "/items/signage_device_tag_map",
                        params={
                            "filter[device_id][_eq]": device_id,
                            "filter[tag_id][_eq]": tag_id,
                        },
                    )
                except Exception:
                    pass
            if tag_id:
                try:
                    await c.delete(f"/items/signage_device_tags/{tag_id}")
                except Exception:
                    pass
            if device_id:
                try:
                    await c.delete(f"/items/signage_devices/{device_id}")
                except Exception:
                    pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_calibration_patch_does_not_fire_device_changed(
    directus_admin_token: str,
) -> None:
    """Phase 70 D-07 case 4: PATCH /api/signage/devices/{id}/calibration
    fires `calibration-changed` AND must NOT fire any subsequent
    `device-changed` event within 1500 ms.

    Pins success criterion #4 at the infra level: the v1_22 trigger
    `signage_devices_update_notify` WHEN-gate
    (backend/alembic/versions/v1_22_signage_notify_triggers.py:128 —
    `WHEN OLD.name IS DISTINCT FROM NEW.name`) excludes calibration columns
    (rotation, hdmi_mode, audio_enabled, last_seen_at, revoked_at) from
    firing the LISTEN trigger. So a calibration-only update path emits the
    FastAPI in-process `calibration-changed` event but NOT the LISTEN-bridge
    `device-changed` event.

    Complements the existing
    `test_calibration_patch_fires_single_frame_no_device_changed_double`
    case but with the explicit Phase 70 naming (D-07 case 4) and a longer
    1500 ms negative-assertion window per plan.
    """
    headers = {"Authorization": f"Bearer {directus_admin_token}"}
    device_id: str | None = None

    async with httpx.AsyncClient(
        headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
    ) as c:
        device_id = await _create_transient_device(
            c, name=f"phase70-calib-{int(time.time() * 1000)}"
        )

    try:
        device_jwt = _get_device_jwt(device_id)
        async with httpx.AsyncClient(
            base_url=API_BASE_URL,
            timeout=10,
            headers={"Authorization": f"Bearer {device_jwt}"},
        ) as api_client:
            async with open_sse_stream(device_id) as stream:
                await _drain_events(stream, settle_ms=200)

                t0 = time.monotonic()
                r = await api_client.patch(
                    f"/api/signage/devices/{device_id}/calibration",
                    json={"rotation": 90},
                )
                assert r.status_code in (200, 204), (
                    f"calibration PATCH failed: {r.status_code} {r.text}"
                )

                # First frame must be calibration-changed within 500 ms.
                first = await asyncio.wait_for(stream.next_frame(), timeout=SSE_TIMEOUT_S)
                first_ms = (time.monotonic() - t0) * 1000
                assert first["event"] == "calibration-changed", (
                    f"expected calibration-changed first, got {first['event']!r}"
                )
                assert first_ms < SSE_TIMEOUT_MS, (
                    f"calibration first-event latency {first_ms:.0f} ms > {SSE_TIMEOUT_MS} ms"
                )

                # Negative assertion: NO device-changed within 1500 ms.
                # Proves the WHEN-gate (v1_22 line 128) excludes calibration
                # columns from signage_devices_update_notify.
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(stream.next_frame(), timeout=1.5)

                logger.info(
                    "phase70 calibration no-double-fire confirmed; "
                    "calibration-changed first-event latency: %.0fms",
                    first_ms,
                )
    finally:
        if device_id is not None:
            async with httpx.AsyncClient(
                headers=headers, base_url=DIRECTUS_BASE_URL, timeout=10
            ) as c:
                try:
                    await c.delete(f"/items/signage_devices/{device_id}")
                except Exception:
                    pass
