"""Unit+integration tests for app.services.signage_resolver — SGN-BE-06.

Covers decisions:
  - D-06: empty envelope on no-tags / no-match / disabled-match
  - D-07: item field population + position ASC ordering
  - D-08: priority DESC, updated_at DESC tie-break, LIMIT 1
  - D-10: resolver never mutates last_seen_at (pure read)

Seeding uses asyncpg for the atomic SQL rows, then the resolver is driven via
the project's AsyncSession (SQLAlchemy 2.0) so we exercise the actual ORM
relationship loading (`selectinload`) the production code relies on.

Skips cleanly when POSTGRES_* is absent so `pytest --collect-only` on a
partial tree still passes.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.database import AsyncSessionLocal, engine
from app.models.signage import SignageDevice
from app.services.signage_resolver import (
    compute_playlist_etag,
    devices_affected_by_device_update,
    devices_affected_by_playlist,
    resolve_playlist_for_device,
)


# --------------------------------------------------------------------------
# Fixture plumbing — mirrors backend/tests/test_signage_pair_router.py
# --------------------------------------------------------------------------


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
        pytest.skip("POSTGRES_* not set — resolver tests need a live DB")
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
        await conn.execute("DELETE FROM signage_playlist_items")
        await conn.execute("DELETE FROM signage_playlist_tag_map")
        await conn.execute("DELETE FROM signage_device_tag_map")
        await conn.execute("DELETE FROM signage_playlists")
        await conn.execute("DELETE FROM signage_devices")
        await conn.execute("DELETE FROM signage_device_tags")
        await conn.execute("DELETE FROM signage_media")
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def dsn():
    d = await _require_db()
    await _cleanup(d)
    # Dispose the engine pool so this test's event loop gets fresh connections.
    try:
        await engine.dispose()
    except Exception:
        pass
    yield d
    await _cleanup(d)


# --------------------------------------------------------------------------
# Seeding helpers (asyncpg)
# --------------------------------------------------------------------------


async def _insert_device(dsn: str, *, name: str = "pi-1") -> uuid.UUID:
    device_id = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_devices (id, name, status) VALUES ($1, $2, 'online')",
            device_id,
            name,
        )
    finally:
        await conn.close()
    return device_id


async def _insert_tag(dsn: str, name: str) -> int:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        row = await conn.fetchrow(
            "INSERT INTO signage_device_tags (name) VALUES ($1) RETURNING id", name
        )
    finally:
        await conn.close()
    return row["id"]


async def _tag_device(dsn: str, device_id: uuid.UUID, tag_id: int) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_device_tag_map (device_id, tag_id) VALUES ($1, $2)",
            device_id,
            tag_id,
        )
    finally:
        await conn.close()


async def _insert_playlist(
    dsn: str,
    *,
    name: str,
    priority: int = 0,
    enabled: bool = True,
    updated_at: datetime | None = None,
) -> uuid.UUID:
    pid = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        if updated_at is None:
            await conn.execute(
                "INSERT INTO signage_playlists (id, name, priority, enabled)"
                " VALUES ($1, $2, $3, $4)",
                pid,
                name,
                priority,
                enabled,
            )
        else:
            await conn.execute(
                "INSERT INTO signage_playlists (id, name, priority, enabled, updated_at)"
                " VALUES ($1, $2, $3, $4, $5)",
                pid,
                name,
                priority,
                enabled,
                updated_at,
            )
    finally:
        await conn.close()
    return pid


async def _tag_playlist(dsn: str, playlist_id: uuid.UUID, tag_id: int) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_playlist_tag_map (playlist_id, tag_id) VALUES ($1, $2)",
            playlist_id,
            tag_id,
        )
    finally:
        await conn.close()


async def _insert_media(
    dsn: str,
    *,
    kind: str = "image",
    title: str = "m",
    uri: str = "/media/x.png",
) -> uuid.UUID:
    mid = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_media (id, kind, title, uri) VALUES ($1, $2, $3, $4)",
            mid,
            kind,
            title,
            uri,
        )
    finally:
        await conn.close()
    return mid


async def _insert_item(
    dsn: str,
    *,
    playlist_id: uuid.UUID,
    media_id: uuid.UUID,
    position: int,
    duration_s: int = 10,
    transition: str | None = "fade",
) -> uuid.UUID:
    iid = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_playlist_items"
            " (id, playlist_id, media_id, position, duration_s, transition)"
            " VALUES ($1, $2, $3, $4, $5, $6)",
            iid,
            playlist_id,
            media_id,
            position,
            duration_s,
            transition,
        )
    finally:
        await conn.close()
    return iid


async def _load_device(db, device_id: uuid.UUID) -> SignageDevice:
    stmt = select(SignageDevice).where(SignageDevice.id == device_id)
    return (await db.execute(stmt)).scalar_one()


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolver_empty_envelope_when_device_has_no_tags(dsn):
    device_id = await _insert_device(dsn)
    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env = await resolve_playlist_for_device(db, device)
    assert env.playlist_id is None
    assert env.name is None
    assert env.items == []
    assert env.resolved_at is not None


@pytest.mark.asyncio
async def test_resolver_empty_envelope_when_no_playlist_matches(dsn):
    device_id = await _insert_device(dsn)
    t1 = await _insert_tag(dsn, "lobby")
    t2 = await _insert_tag(dsn, "cafeteria")
    await _tag_device(dsn, device_id, t1)

    # Playlist exists but is tagged to t2 (cafeteria), not device's t1 (lobby).
    pid = await _insert_playlist(dsn, name="cafe-playlist", priority=10)
    await _tag_playlist(dsn, pid, t2)

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env = await resolve_playlist_for_device(db, device)
    assert env.playlist_id is None
    assert env.items == []


@pytest.mark.asyncio
async def test_resolver_empty_envelope_when_match_is_disabled(dsn):
    device_id = await _insert_device(dsn)
    t1 = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t1)

    pid = await _insert_playlist(dsn, name="disabled", priority=10, enabled=False)
    await _tag_playlist(dsn, pid, t1)

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env = await resolve_playlist_for_device(db, device)
    assert env.playlist_id is None
    assert env.items == []


@pytest.mark.asyncio
async def test_resolver_returns_highest_priority_playlist(dsn):
    device_id = await _insert_device(dsn)
    t1 = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t1)

    low = await _insert_playlist(dsn, name="low", priority=5)
    high = await _insert_playlist(dsn, name="high", priority=10)
    await _tag_playlist(dsn, low, t1)
    await _tag_playlist(dsn, high, t1)

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env = await resolve_playlist_for_device(db, device)
    assert env.playlist_id == high
    assert env.name == "high"


@pytest.mark.asyncio
async def test_resolver_priority_tie_broken_by_updated_at_desc(dsn):
    device_id = await _insert_device(dsn)
    t1 = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t1)

    older = datetime.now(timezone.utc) - timedelta(days=2)
    newer = datetime.now(timezone.utc) - timedelta(minutes=1)
    old_pid = await _insert_playlist(
        dsn, name="older", priority=5, updated_at=older
    )
    new_pid = await _insert_playlist(
        dsn, name="newer", priority=5, updated_at=newer
    )
    await _tag_playlist(dsn, old_pid, t1)
    await _tag_playlist(dsn, new_pid, t1)

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env = await resolve_playlist_for_device(db, device)
    assert env.playlist_id == new_pid
    assert env.name == "newer"


@pytest.mark.asyncio
async def test_resolver_items_ordered_by_position_asc(dsn):
    device_id = await _insert_device(dsn)
    t1 = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t1)

    pid = await _insert_playlist(dsn, name="ordered", priority=1)
    await _tag_playlist(dsn, pid, t1)

    m1 = await _insert_media(dsn, kind="image", title="first", uri="/a.png")
    m2 = await _insert_media(dsn, kind="image", title="second", uri="/b.png")
    m3 = await _insert_media(dsn, kind="image", title="third", uri="/c.png")

    # Insert out of order to prove ordering is enforced by resolver.
    await _insert_item(dsn, playlist_id=pid, media_id=m3, position=3)
    await _insert_item(dsn, playlist_id=pid, media_id=m1, position=1)
    await _insert_item(dsn, playlist_id=pid, media_id=m2, position=2)

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env = await resolve_playlist_for_device(db, device)
    assert [i.position for i in env.items] == [1, 2, 3]
    # Confirm ordering is backed by media identity, not just position column
    assert [i.media_id for i in env.items] == [m1, m2, m3]


@pytest.mark.asyncio
async def test_resolver_item_fields_populated(dsn):
    device_id = await _insert_device(dsn)
    t1 = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t1)

    pid = await _insert_playlist(dsn, name="full", priority=1)
    await _tag_playlist(dsn, pid, t1)

    m = await _insert_media(dsn, kind="video", title="clip", uri="/v.mp4")
    await _insert_item(
        dsn, playlist_id=pid, media_id=m, position=1, duration_s=7, transition="fade"
    )

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env = await resolve_playlist_for_device(db, device)
    assert len(env.items) == 1
    item = env.items[0]
    assert item.media_id == m
    assert item.kind == "video"
    assert item.uri == "/v.mp4"
    assert item.duration_ms == 7000  # duration_s * 1000
    assert item.transition == "fade"
    assert item.position == 1


@pytest.mark.asyncio
async def test_resolver_does_not_mutate_last_seen_at(dsn):
    """D-10: resolver is a pure read — last_seen_at remains untouched."""
    device_id = await _insert_device(dsn)
    t1 = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t1)

    pid = await _insert_playlist(dsn, name="p", priority=1)
    await _tag_playlist(dsn, pid, t1)

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        assert device.last_seen_at is None
        await resolve_playlist_for_device(db, device)

    # Re-read via a fresh asyncpg connection to side-step ORM caches.
    conn = await asyncpg.connect(dsn=dsn)
    try:
        row = await conn.fetchrow(
            "SELECT last_seen_at FROM signage_devices WHERE id = $1", device_id
        )
    finally:
        await conn.close()
    assert row["last_seen_at"] is None


# --------------------------------------------------------------------------
# compute_playlist_etag (D-09 helper; used by Plan 04 router)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_playlist_etag_stable_for_empty(dsn):
    from app.schemas.signage import PlaylistEnvelope

    env = PlaylistEnvelope(
        playlist_id=None,
        name=None,
        items=[],
        resolved_at=datetime.now(timezone.utc),
    )
    etag1 = compute_playlist_etag(env)
    etag2 = compute_playlist_etag(env)
    assert isinstance(etag1, str) and len(etag1) == 64  # sha256 hex
    assert etag1 == etag2


@pytest.mark.asyncio
async def test_compute_playlist_etag_changes_with_content(dsn):
    device_id = await _insert_device(dsn)
    t1 = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t1)

    pid = await _insert_playlist(dsn, name="p", priority=1)
    await _tag_playlist(dsn, pid, t1)

    m1 = await _insert_media(dsn, kind="image", title="a", uri="/a.png")
    await _insert_item(dsn, playlist_id=pid, media_id=m1, position=1)

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env_a = await resolve_playlist_for_device(db, device)
    etag_a = compute_playlist_etag(env_a)

    # Add a second item — etag must change.
    m2 = await _insert_media(dsn, kind="image", title="b", uri="/b.png")
    await _insert_item(dsn, playlist_id=pid, media_id=m2, position=2)

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env_b = await resolve_playlist_for_device(db, device)
    etag_b = compute_playlist_etag(env_b)

    assert etag_a != etag_b


# --------------------------------------------------------------------------
# devices_affected_by_playlist / devices_affected_by_device_update
# (Plan 45-01 — broadcast fanout resolver helper)
# --------------------------------------------------------------------------


async def _revoke_device(dsn: str, device_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "UPDATE signage_devices SET revoked_at = now() WHERE id = $1",
            device_id,
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_devices_affected_by_playlist_returns_tag_overlap(dsn):
    d1 = await _insert_device(dsn, name="pi-lobby")
    d2 = await _insert_device(dsn, name="pi-kitchen")
    d3 = await _insert_device(dsn, name="pi-lobby-office")

    t_lobby = await _insert_tag(dsn, "lobby")
    t_kitchen = await _insert_tag(dsn, "kitchen")
    t_office = await _insert_tag(dsn, "office")

    await _tag_device(dsn, d1, t_lobby)
    await _tag_device(dsn, d2, t_kitchen)
    await _tag_device(dsn, d3, t_lobby)
    await _tag_device(dsn, d3, t_office)

    pid = await _insert_playlist(dsn, name="lobby-playlist", priority=1)
    await _tag_playlist(dsn, pid, t_lobby)

    async with AsyncSessionLocal() as db:
        affected = await devices_affected_by_playlist(db, pid)

    assert affected == sorted([d1, d3])


@pytest.mark.asyncio
async def test_devices_affected_by_playlist_excludes_revoked_devices(dsn):
    d1 = await _insert_device(dsn, name="pi-live")
    d2 = await _insert_device(dsn, name="pi-revoked")
    t = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, d1, t)
    await _tag_device(dsn, d2, t)
    await _revoke_device(dsn, d2)

    pid = await _insert_playlist(dsn, name="p", priority=1)
    await _tag_playlist(dsn, pid, t)

    async with AsyncSessionLocal() as db:
        affected = await devices_affected_by_playlist(db, pid)

    assert affected == [d1]


@pytest.mark.asyncio
async def test_devices_affected_by_playlist_empty_for_untagged_playlist(dsn):
    # Device exists and is tagged, but the playlist itself has no target-tag rows.
    d = await _insert_device(dsn)
    t = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, d, t)

    pid = await _insert_playlist(dsn, name="no-targets", priority=1)

    async with AsyncSessionLocal() as db:
        affected = await devices_affected_by_playlist(db, pid)

    assert affected == []


@pytest.mark.asyncio
async def test_devices_affected_by_device_update_returns_single_id(dsn):
    d = await _insert_device(dsn)
    async with AsyncSessionLocal() as db:
        affected = await devices_affected_by_device_update(db, d)
    assert affected == [d]
