"""Admin-facing SSE stream — fan-out of signage_change events to admin UIs.

Endpoint: ``GET /api/signage/admin/stream``.

The frontend hook ``useAdminSignageEvents`` (frontend/src/signage/lib/
useAdminSignageEvents.ts) opens an EventSource against this endpoint and
invalidates TanStack Query caches based on the ``event`` field in the
payload. Best-effort: admin mutations already invalidate locally, so a
dropped connection only loses cross-session updates.

Payload shape (mirrors signage_pg_listen.notify_admin):
    {"event": "playlist-changed"|"schedule-changed"|"device-changed",
     "table": "<source table>", "op": "INSERT"|"UPDATE"|"DELETE"}

Auth: EventSource cannot send custom headers, so cookie auth is the only
option. The router-level ``get_current_user`` + ``require_admin`` gates in
signage_admin/__init__.py cover this — ``get_current_user`` accepts the
Directus session cookie (commit 23ecbf1).

--workers 1 invariant applies (admin queues are process-local; see
signage_broadcast.py docstring).

Compute-justified: clause 1 (SSE fan-out) — a long-lived Server-Sent-Events
stream over a process-local queue; not expressible as a Directus read.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.services import signage_broadcast

router = APIRouter(prefix="/admin", tags=["signage-admin-stream"])


@router.get("/stream")
async def stream_admin_events() -> EventSourceResponse:
    """SSE: streams every signage_change event to the connecting admin.

    ``ping=15`` emits a keepalive comment every 15s so idle intermediaries
    (Caddy, browsers) don't close the connection. ``asyncio.CancelledError``
    is re-raised so the queue is always cleaned up on disconnect.
    """
    queue = signage_broadcast.subscribe_admin()

    async def event_generator():
        try:
            while True:
                payload = await queue.get()
                yield {"data": json.dumps(payload)}
        except asyncio.CancelledError:
            raise
        finally:
            signage_broadcast.unsubscribe_admin(queue)

    return EventSourceResponse(event_generator(), ping=15)
