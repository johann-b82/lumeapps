"""SSE fanout substrate for signage devices (SGN-BE-05, SGN-INF-03).

Per-device in-process ``asyncio.Queue`` fanout. Admin mutation hooks
(Plan 45-02) call ``notify_device(device_id, payload)``; the SSE
``GET /api/signage/player/stream`` endpoint (Plan 45-02) calls
``subscribe(device_id)`` to receive a queue it can ``await`` on. Drop-
oldest overflow (D-04) and fan-out to ALL subscribers per device (replacing
the previous last-writer-wins D-03 design — see Phase 74.2 bug-fix note
below).

-----------------------------------------------------------------------
Fan-out design change (pi-sidecar-sse-loop-silent fix)
-----------------------------------------------------------------------

The original D-03 last-writer-wins design stored one queue per device in
``_device_queues``.  In production each device has TWO concurrent SSE
subscribers:

1. The Pi sidecar ``_calibration_sse_loop`` — opens
   ``GET /api/signage/player/stream`` with ``Authorization: Bearer``.
2. The Chromium kiosk player — opens the same endpoint with ``?token=``.

Under last-writer-wins the browser's ``subscribe()`` call replaced the
sidecar's queue.  ``notify_device()`` then delivered calibration-changed
events only to the browser; the sidecar's generator was blocked on a now-
orphaned queue and never invoked ``_apply_calibration``.  The result was
complete silence on the Pi (no rotation, no calibration.json) even though
the PATCH returned 200 and the DB updated correctly.

Fix: ``_device_queues`` now maps ``device_id`` → ``list[asyncio.Queue]``.
``subscribe()`` appends a fresh queue to the list; ``notify_device()``
delivers to ALL queues in the list; ``unsubscribe()`` removes a specific
queue by identity.  The SSE endpoint's ``finally`` block calls
``unsubscribe(device_id, queue)`` instead of popping the whole key.

-----------------------------------------------------------------------
--workers 1 INVARIANT (cross-cutting hazard #4)
-----------------------------------------------------------------------

1. Single-process only. This module owns a process-local
   ``_device_queues`` dict. Running uvicorn with ``--workers N`` for any
   N > 1 gives each worker its own disjoint dict; an admin mutation
   handled in worker A will call ``notify_device`` on worker A's dict,
   but the SSE generator for a given device may be pinned to worker B
   (round-robin) — that subscriber will never see the event.

2. Why the constraint exists. SSE fanout here intentionally uses an
   in-memory per-device queue instead of Redis / pub-sub precisely so
   the small-fleet (≤5 devices) signage loop stays zero-infra. The
   trade-off is correctness requires single-process. This matches the
   existing APScheduler in-memory jobstore constraint in
   ``backend/app/scheduler.py`` and the deployment-level pin in
   ``docker-compose.yml`` (``uvicorn ... --workers 1``).

3. What breaks under multi-worker. Roughly ``(N-1)/N`` of SSE clients
   silently miss events (no error, no log — the notify side has no
   visibility into which worker owns each subscriber). The 30s polling
   loop in Plan 43 would still catch up eventually, but the SSE value
   proposition (instant playlist updates) is destroyed. Any future
   horizontal-scaling plan MUST extract the broadcast path into a
   separate container with a shared bus before bumping ``--workers``.

See ``docker-compose.yml`` (``--workers 1`` uvicorn command) and
``backend/app/scheduler.py`` (PITFALLS C-7) for the paired invariants.
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)

# Maps device_id → list of active subscriber queues.
# Multiple subscribers per device are supported (sidecar + browser both
# subscribe simultaneously).  notify_device() delivers to all of them.
_device_queues: dict[int, list[asyncio.Queue]] = {}


def subscribe(device_id: int) -> asyncio.Queue:
    """Register a fresh fanout queue for ``device_id`` and return it.

    Appends to the per-device subscriber list (fan-out semantics).
    Each concurrent SSE connection for the same device gets its own queue;
    ``notify_device`` delivers to all of them.

    Call ``unsubscribe(device_id, queue)`` in the generator's ``finally``
    block to clean up when the connection closes.
    """
    q: asyncio.Queue = asyncio.Queue(maxsize=32)
    if device_id not in _device_queues:
        _device_queues[device_id] = []
    _device_queues[device_id].append(q)
    return q


def unsubscribe(device_id: int, queue: asyncio.Queue) -> None:
    """Remove a specific queue from the per-device subscriber list.

    Uses identity (``is``) comparison so only the exact queue instance is
    removed.  If no queues remain for the device, the device key is pruned.
    No-op if the queue is not present (safe to call from finally blocks).
    """
    queues = _device_queues.get(device_id)
    if queues is None:
        return
    _device_queues[device_id] = [q for q in queues if q is not queue]
    if not _device_queues[device_id]:
        del _device_queues[device_id]


def notify_device(device_id: int, payload: dict) -> None:
    """Enqueue ``payload`` for ALL of ``device_id``'s subscribers.

    Synchronous — uses ``put_nowait`` so admin mutation handlers in
    Plan 02 can call this inside a BackgroundTasks hook without await.

    D-04 (drop-oldest + WARN-once): on ``asyncio.QueueFull`` we drop the
    FIFO-head event, emit a WARN log exactly once per connection (flag
    stashed on the queue instance), then enqueue the new payload. A new
    subscriber (via ``subscribe``) gets a fresh Queue without the flag,
    so the next connection can warn again — Pitfall 7.

    Log format uses ``%s``-style args (NOT f-strings) to satisfy the
    Phase 43 CI grep guard that forbids f-strings inside log format
    arguments.
    """
    queues = _device_queues.get(device_id)
    if not queues:
        return
    for q in queues:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            if not getattr(q, "_warned_full", False):
                log.warning(
                    "signage broadcast queue full for device %s (depth=%s) —"
                    " dropping oldest",
                    device_id,
                    q.qsize(),
                )
                q._warned_full = True  # type: ignore[attr-defined]
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            q.put_nowait(payload)


# ---------------------------------------------------------------------------
# Phase A — high-level notify_* helpers consolidated from signage_admin/*.py.
# These replace the four inline ``_notify_*`` duplicates that previously
# lived in playlists.py, playlist_items.py, media.py, and devices.py.
#
# Invariants:
#   1. Helpers DO NOT commit. Caller commits, then calls the helper.
#   2. ``notify_playlist_changed(..., affected=[...], deleted=True)`` is the
#      DELETE path: caller pre-computes ``affected`` BEFORE commit (because
#      tag-map cascade invalidates the query post-commit), then commits, then
#      calls the helper with ``deleted=True`` so the literal etag "deleted"
#      is broadcast.
#   3. Low-level ``notify_device(device_id, payload)`` above stays as-is.
# ---------------------------------------------------------------------------

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Imported lazily inside functions to avoid import-time cycles with models/.
from app.services.signage_resolver import (  # noqa: E402
    compute_playlist_etag,
    devices_affected_by_playlist,
    resolve_playlist_for_device,
)


async def _load_device(db: "AsyncSession", device_id: int):
    from app.models import SignageDevice
    return (await db.execute(select(SignageDevice).where(SignageDevice.id == device_id))).scalar_one_or_none()


async def _playlists_referencing_media(db: "AsyncSession", media_id: UUID) -> list[UUID]:
    from app.models import SignagePlaylistItem
    rows = await db.execute(
        select(SignagePlaylistItem.playlist_id)
        .where(SignagePlaylistItem.media_id == media_id)
        .distinct()
    )
    return list(rows.scalars().all())


async def notify_playlist_changed(
    db: "AsyncSession",
    playlist_id: UUID,
    *,
    affected: list[int] | None = None,
    deleted: bool = False,
) -> None:
    """Broadcast playlist-changed to every device whose envelope is affected.

    Default path resolves affected devices and re-resolves their envelope etag.
    DELETE path passes pre-computed ``affected`` and ``deleted=True``; this
    skips the resolver and emits the literal etag ``"deleted"`` so the
    player invalidates without trying to fetch a now-deleted playlist.
    """
    if deleted:
        if affected is None:
            raise ValueError("deleted=True requires pre-computed affected= list")
        for device_id in affected:
            notify_device(
                device_id,
                {"event": "playlist-changed", "playlist_id": str(playlist_id), "etag": "deleted"},
            )
        return

    device_ids = affected if affected is not None else await devices_affected_by_playlist(db, playlist_id)
    for device_id in device_ids:
        dev = await _load_device(db, device_id)
        if dev is None:
            continue
        envelope = await resolve_playlist_for_device(db, dev)
        notify_device(
            device_id,
            {
                "event": "playlist-changed",
                "playlist_id": str(playlist_id),
                "etag": compute_playlist_etag(envelope),
            },
        )


async def notify_devices_for_media(db: "AsyncSession", media_id: UUID) -> None:
    """Fan out playlist-changed for every playlist that references this media."""
    for pid in await _playlists_referencing_media(db, media_id):
        await notify_playlist_changed(db, pid)


async def notify_device_self(db: "AsyncSession", device_id: int) -> None:
    """Notify a single device its own resolved envelope changed (e.g. tag edit)."""
    dev = await _load_device(db, device_id)
    if dev is None:
        return
    envelope = await resolve_playlist_for_device(db, dev)
    notify_device(
        device_id,
        {"event": "playlist-changed", "device_id": str(device_id), "etag": compute_playlist_etag(envelope)},
    )
