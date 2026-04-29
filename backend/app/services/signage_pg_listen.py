"""Asyncpg LISTEN/NOTIFY bridge for signage SSE (SSE-03, SSE-06).

Long-lived asyncpg connection subscribes to ``signage_change`` and fans
out to player SSE streams via notify_device() + resolver path.

--workers 1 INVARIANT (cross-cutting hazard #4): single process-wide
connection; N>1 workers each get a disjoint connection and may miss
events for devices pinned to another worker. Always deploy ``--workers 1``.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from uuid import UUID

import asyncpg
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.signage import SignageSchedule
from app.services.signage_broadcast import notify_device
from app.services.signage_resolver import (
    devices_affected_by_device_update,
    devices_affected_by_playlist,
)

log = logging.getLogger(__name__)

CHANNEL = "signage_change"
_INITIAL_BACKOFF = 1.0
_MAX_BACKOFF = 30.0


def _pg_dsn() -> str:
    """Build a plain asyncpg DSN from the SQLAlchemy DATABASE_URL env var."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("SYNC_DATABASE_URL", "")
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _handle_notify(conn, pid, channel, payload: str) -> None:  # noqa: ARG001
    """Asyncpg notify callback — dispatches to resolver then notify_device."""
    try:
        data = json.loads(payload)
        table: str = data["table"]
        op: str = data["op"]
        row_id: str = data["id"]
    except (json.JSONDecodeError, KeyError, TypeError):
        log.warning("signage_pg_listen: bad payload %s", payload)
        return

    try:
        async with AsyncSessionLocal() as db:
            if table in (
                "signage_playlists",
                "signage_playlist_items",
                "signage_playlist_tag_map",
            ):
                affected = await devices_affected_by_playlist(db, UUID(row_id))
                event = "playlist-changed"

            elif table == "signage_schedules":
                schedule_id = UUID(row_id)
                result = await db.execute(
                    select(SignageSchedule.playlist_id).where(
                        SignageSchedule.id == schedule_id
                    )
                )
                playlist_id = result.scalar_one_or_none()
                if playlist_id is None:
                    log.debug(
                        "signage_pg_listen: schedule %s not found (op=%s)",
                        schedule_id,
                        op,
                    )
                    affected = []
                else:
                    affected = await devices_affected_by_playlist(db, playlist_id)
                event = "schedule-changed"

            elif table == "signage_devices":
                affected = [UUID(row_id)] if op != "DELETE" else []
                event = "device-changed"

            elif table == "signage_device_tag_map":
                affected = await devices_affected_by_device_update(db, UUID(row_id))
                event = "device-changed"

            else:
                log.debug("signage_pg_listen: unhandled table %s", table)
                return

            for dev_id in affected:
                notify_device(dev_id, {"event": event, "table": table, "op": op})

    except (ValueError, KeyError):
        log.warning("signage_pg_listen: bad payload %s", payload)


async def _listener_loop() -> None:
    """Reconnect loop — runs forever; only CancelledError exits."""
    attempt = 0
    backoff = _INITIAL_BACKOFF

    while True:
        attempt += 1
        conn = None
        try:
            conn = await asyncpg.connect(_pg_dsn())
            await conn.add_listener(CHANNEL, _handle_notify)
            log.info("signage_pg_listen: subscribed to %s", CHANNEL)
            backoff = _INITIAL_BACKOFF  # reset after successful connect
            while not conn.is_closed():
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if attempt == 1:
                log.error(
                    "signage_pg_listen: initial connect failed — retrying in background: %s",
                    exc,
                )
            else:
                log.warning(
                    "signage_pg_listen: reconnecting attempt=%d backoff=%.1fs err=%s",
                    attempt,
                    backoff,
                    exc,
                )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _MAX_BACKOFF)
        finally:
            if conn is not None and not conn.is_closed():
                try:
                    await conn.remove_listener(CHANNEL, _handle_notify)
                except Exception:
                    pass
                try:
                    await conn.close()
                except Exception:
                    pass


async def start(app) -> asyncio.Task:
    """Create and store the listener task on ``app.state``. Fail-soft (D-13)."""
    task = asyncio.create_task(_listener_loop(), name="signage_pg_listen")
    app.state.signage_pg_listen_task = task
    return task


async def stop(app) -> None:
    """Cancel the listener task and await its completion."""
    task: asyncio.Task | None = getattr(app.state, "signage_pg_listen_task", None)
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
