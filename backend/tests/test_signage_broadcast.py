"""Unit tests for app.services.signage_broadcast — SGN-BE-05.

Covers decisions:
  - Fan-out: all active subscribers for a device receive events
  - D-04: drop-oldest + WARN-once per connection on QueueFull
  - unsubscribe: removes only the specific queue, leaves others intact

All tests operate on module-level state with an autouse reset fixture, so
no DB is required. pytest-asyncio handles the event-loop-per-test shape
for Queue() creation.
"""
from __future__ import annotations

import asyncio
import logging

import pytest

from app.services import signage_broadcast


@pytest.fixture(autouse=True)
def _reset_device_queues():
    """Clear the module-level fanout dict between tests to avoid leakage."""
    signage_broadcast._device_queues.clear()
    yield
    signage_broadcast._device_queues.clear()


# --------------------------------------------------------------------------
# A: subscribe creates a Queue with maxsize=32 and registers it
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_creates_queue_with_maxsize_32():
    q = signage_broadcast.subscribe(1)
    assert isinstance(q, asyncio.Queue)
    assert q.maxsize == 32
    assert q in signage_broadcast._device_queues[1]


# --------------------------------------------------------------------------
# B: multiple subscribes for the same device fan-out to all
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_fan_out_multiple_subscribers():
    q1 = signage_broadcast.subscribe(1)
    q2 = signage_broadcast.subscribe(1)
    assert q1 is not q2
    assert q1 in signage_broadcast._device_queues[1]
    assert q2 in signage_broadcast._device_queues[1]
    assert len(signage_broadcast._device_queues[1]) == 2


# --------------------------------------------------------------------------
# C: notify_device is a no-op when no subscriber exists
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_device_noop_when_no_subscriber():
    signage_broadcast.notify_device(999, {"event": "playlist-changed"})
    assert 999 not in signage_broadcast._device_queues


# --------------------------------------------------------------------------
# D: notify_device enqueues the payload on ALL subscriber queues
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_device_enqueues_payload():
    q = signage_broadcast.subscribe(1)
    payload = {"event": "playlist-changed", "playlist_id": 42, "etag": "abc"}
    signage_broadcast.notify_device(1, payload)
    assert q.qsize() == 1
    assert q.get_nowait() == payload


@pytest.mark.asyncio
async def test_notify_device_delivers_to_all_subscribers():
    q1 = signage_broadcast.subscribe(1)
    q2 = signage_broadcast.subscribe(1)
    payload = {"event": "calibration-changed", "device_id": "abc"}
    signage_broadcast.notify_device(1, payload)
    assert q1.get_nowait() == payload
    assert q2.get_nowait() == payload


# --------------------------------------------------------------------------
# E: D-04 drop-oldest — overflow drops FIFO-head, preserves maxsize
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_device_drops_oldest_on_queue_full():
    q = signage_broadcast.subscribe(1)
    for i in range(32):
        q.put_nowait({"n": i})
    assert q.qsize() == 32

    # Overflow push — must drop {"n": 0} (oldest) and append {"n": 999}.
    signage_broadcast.notify_device(1, {"n": 999})
    assert q.qsize() == 32  # size never exceeds maxsize

    drained = []
    while not q.empty():
        drained.append(q.get_nowait())
    # Oldest {"n": 0} was dropped. Head is now {"n": 1}, tail is {"n": 999}.
    assert drained[0] == {"n": 1}
    assert drained[-1] == {"n": 999}
    assert len(drained) == 32


# --------------------------------------------------------------------------
# F: D-04 WARN-once per connection — two overflow calls => one WARNING record
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_device_warns_once_on_first_drop(caplog):
    q = signage_broadcast.subscribe(1)
    for i in range(32):
        q.put_nowait({"n": i})

    with caplog.at_level(logging.WARNING, logger="app.services.signage_broadcast"):
        signage_broadcast.notify_device(1, {"n": 100})
        signage_broadcast.notify_device(1, {"n": 101})

    warnings = [
        r
        for r in caplog.records
        if r.name == "app.services.signage_broadcast"
        and r.levelno == logging.WARNING
    ]
    assert len(warnings) == 1, f"expected exactly 1 WARN, got {len(warnings)}"
    msg = warnings[0].getMessage()
    assert "1" in msg, "device id should appear in message"
    assert "32" in msg, "queue depth should appear in message"


# --------------------------------------------------------------------------
# G: warn-once flag is per-queue — a new subscribe() gets a fresh queue
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_warned_flag_reset_on_resubscribe(caplog):
    q1 = signage_broadcast.subscribe(1)
    for i in range(32):
        q1.put_nowait({"n": i})

    with caplog.at_level(logging.WARNING, logger="app.services.signage_broadcast"):
        # First overflow on q1 — first warn fires.
        signage_broadcast.notify_device(1, {"n": 100})

        # Unsubscribe q1, add a new q2.  The new queue has no `_warned_full`
        # attr, so the next overflow must warn again.
        signage_broadcast.unsubscribe(1, q1)
        q2 = signage_broadcast.subscribe(1)
        assert q2 is not q1
        for i in range(32):
            q2.put_nowait({"m": i})
        signage_broadcast.notify_device(1, {"m": 200})

    warnings = [
        r
        for r in caplog.records
        if r.name == "app.services.signage_broadcast"
        and r.levelno == logging.WARNING
    ]
    assert len(warnings) == 2, (
        f"expected 2 warns (one per connection), got {len(warnings)}"
    )


# --------------------------------------------------------------------------
# H: unsubscribe removes only the specific queue, preserves others
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unsubscribe_removes_specific_queue_only():
    q1 = signage_broadcast.subscribe(1)
    q2 = signage_broadcast.subscribe(1)
    signage_broadcast.unsubscribe(1, q1)
    assert q1 not in signage_broadcast._device_queues[1]
    assert q2 in signage_broadcast._device_queues[1]


@pytest.mark.asyncio
async def test_unsubscribe_last_queue_prunes_device_key():
    q1 = signage_broadcast.subscribe(1)
    signage_broadcast.unsubscribe(1, q1)
    assert 1 not in signage_broadcast._device_queues


@pytest.mark.asyncio
async def test_unsubscribe_noop_when_queue_not_present():
    q_orphan = asyncio.Queue()
    signage_broadcast.unsubscribe(1, q_orphan)  # must not raise
    assert 1 not in signage_broadcast._device_queues
