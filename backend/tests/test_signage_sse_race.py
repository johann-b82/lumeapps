"""Phase 74.2 SSE-01a regression + pi-sidecar-sse-loop-silent fix.

Tests two distinct races:

1. Overlapping-subscribe cleanup race (Phase 74.2 SSE-01a):
   An old generator's late-running finally MUST NOT clobber a newer
   connection's queue.  Fixed via ``unsubscribe(device_id, queue)`` which
   removes only the caller's queue by identity.

2. Simultaneous-subscriber fan-out (pi-sidecar-sse-loop-silent):
   When two connections subscribe for the same device (Pi sidecar +
   Chromium kiosk browser), both must receive events.  ``notify_device``
   delivers to all queues in the per-device list.

These tests are deterministic — no asyncio scheduling games needed.
"""
from __future__ import annotations

import asyncio

import pytest

from app.services import signage_broadcast


@pytest.fixture(autouse=True)
def _reset_device_queues():
    signage_broadcast._device_queues.clear()
    yield
    signage_broadcast._device_queues.clear()


def _generator_finally(device_id: int, queue: asyncio.Queue) -> None:
    """Mirror of the finally block in signage_player.stream_events."""
    signage_broadcast.unsubscribe(device_id, queue)


# ---------------------------------------------------------------------------
# Race 1 (Phase 74.2): old generator finally does not affect other queues
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_old_generator_finally_does_not_clobber_new_subscriber():
    # Connection #1 subscribes
    q1 = signage_broadcast.subscribe(1)
    assert q1 in signage_broadcast._device_queues[1]

    # Connection #2 also subscribes (concurrent — fan-out model)
    q2 = signage_broadcast.subscribe(1)
    assert q2 in signage_broadcast._device_queues[1]

    # Connection #1 closes and its finally runs
    _generator_finally(1, q1)

    # q2 MUST still be registered
    assert 1 in signage_broadcast._device_queues
    assert q2 in signage_broadcast._device_queues[1]
    assert q1 not in signage_broadcast._device_queues[1]


@pytest.mark.asyncio
async def test_notify_device_after_race_delivers_to_newer_queue():
    q1 = signage_broadcast.subscribe(1)
    q2 = signage_broadcast.subscribe(1)
    _generator_finally(1, q1)  # q1 unsubscribed

    payload = {"event": "calibration-changed", "device_id": "abc"}
    signage_broadcast.notify_device(1, payload)

    # q2 receives the event
    assert q2.get_nowait() == payload
    # q1 is orphaned — nothing in it
    assert q1.empty()


@pytest.mark.asyncio
async def test_single_subscriber_clean_shutdown_still_removes_queue():
    q1 = signage_broadcast.subscribe(1)
    _generator_finally(1, q1)
    assert 1 not in signage_broadcast._device_queues


# ---------------------------------------------------------------------------
# Race 2 (pi-sidecar-sse-loop-silent): two simultaneous subscribers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_simultaneous_subscribers_both_receive_event():
    """Sidecar + browser both subscribed: both must get calibration-changed."""
    q_sidecar = signage_broadcast.subscribe(1)
    q_browser = signage_broadcast.subscribe(1)

    payload = {"event": "calibration-changed", "device_id": "abc"}
    signage_broadcast.notify_device(1, payload)

    assert q_sidecar.get_nowait() == payload
    assert q_browser.get_nowait() == payload


@pytest.mark.asyncio
async def test_browser_disconnect_does_not_affect_sidecar():
    """Browser closing its connection must not starve the sidecar."""
    q_sidecar = signage_broadcast.subscribe(1)
    q_browser = signage_broadcast.subscribe(1)

    # Browser disconnects
    _generator_finally(1, q_browser)

    payload = {"event": "calibration-changed", "device_id": "abc"}
    signage_broadcast.notify_device(1, payload)

    # Sidecar still receives
    assert q_sidecar.get_nowait() == payload
    # Browser queue is orphaned
    assert q_browser.empty()
