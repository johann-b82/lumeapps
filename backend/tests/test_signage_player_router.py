"""Integration tests for /api/signage/player/* — SGN-BE-02 (Phase 43-04).

Covers decisions:
  - D-02: router-level device-token gate (no user JWT accepted)
  - D-06 / D-07: tag-resolved playlist envelope shape
  - D-09: ETag round-trip; If-None-Match -> 304
  - D-10: GET /playlist does NOT mutate signage_devices.last_seen_at
  - D-11 / D-12: POST /heartbeat updates presence, flips offline->online, 204

Seeding uses asyncpg against the live database; tokens are minted with
``app.services.signage_pairing.mint_device_jwt``. Skips cleanly when
``POSTGRES_*`` env is not set so ``pytest --collect-only`` on partial trees
remains green.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest
import pytest_asyncio

from app.services.signage_pairing import mint_device_jwt
from tests.test_directus_auth import _mint as _mint_user_jwt, ADMIN_UUID


# --------------------------------------------------------------------------
# DSN / skip helpers (mirrors other signage tests)
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
        pytest.skip("POSTGRES_* not set — player router tests need a live DB")
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


# --------------------------------------------------------------------------
# Seed helpers
# --------------------------------------------------------------------------


async def _insert_device(
    dsn: str,
    *,
    status: str = "online",
    last_seen_at: datetime | None = None,
) -> uuid.UUID:
    device_id = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_devices (id, name, status, last_seen_at)"
            " VALUES ($1, $2, $3, $4)",
            device_id,
            f"pi-{device_id.hex[:6]}",
            status,
            last_seen_at,
        )
    finally:
        await conn.close()
    return device_id


async def _fetch_device(dsn: str, device_id: uuid.UUID):
    conn = await asyncpg.connect(dsn=dsn)
    try:
        return await conn.fetchrow(
            "SELECT id, status, last_seen_at, current_item_id,"
            " current_playlist_etag FROM signage_devices WHERE id = $1",
            device_id,
        )
    finally:
        await conn.close()


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


async def _insert_playlist(dsn: str, *, name: str, priority: int = 0) -> uuid.UUID:
    pid = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_playlists (id, name, priority, enabled)"
            " VALUES ($1, $2, $3, true)",
            pid,
            name,
            priority,
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


async def _insert_media(dsn: str, *, title: str = "m") -> uuid.UUID:
    mid = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_media (id, kind, title, uri)"
            " VALUES ($1, 'image', $2, '/media/x.png')",
            mid,
            title,
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
) -> uuid.UUID:
    iid = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_playlist_items"
            " (id, playlist_id, media_id, position, duration_s, transition)"
            " VALUES ($1, $2, $3, $4, $5, 'fade')",
            iid,
            playlist_id,
            media_id,
            position,
            duration_s,
        )
    finally:
        await conn.close()
    return iid


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


async def _seed_matched_playlist(dsn: str, *, device_id: uuid.UUID) -> uuid.UUID:
    """Seed one tag + one device-tag + one enabled playlist with two items.

    Returns the playlist id.
    """
    tag_id = await _insert_tag(dsn, f"lobby-{uuid.uuid4().hex[:6]}")
    await _tag_device(dsn, device_id, tag_id)
    pid = await _insert_playlist(dsn, name="match", priority=10)
    await _tag_playlist(dsn, pid, tag_id)
    m1 = await _insert_media(dsn, title="slide-1")
    m2 = await _insert_media(dsn, title="slide-2")
    await _insert_item(dsn, playlist_id=pid, media_id=m1, position=1)
    await _insert_item(dsn, playlist_id=pid, media_id=m2, position=2)
    return pid


# --------------------------------------------------------------------------
# GET /api/signage/player/playlist
# --------------------------------------------------------------------------


async def test_playlist_requires_device_token(client, dsn):
    r = await client.get("/api/signage/player/playlist")
    assert r.status_code == 401, r.text


async def test_playlist_rejects_user_jwt(client, dsn):
    # Regular Directus admin JWT is NOT a device token (scope != "device").
    token = _mint_user_jwt(ADMIN_UUID)
    r = await client.get(
        "/api/signage/player/playlist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401, r.text


async def test_playlist_returns_envelope_for_device(client, dsn):
    device_id = await _insert_device(dsn, status="online")
    await _seed_matched_playlist(dsn, device_id=device_id)
    token = mint_device_jwt(device_id)

    r = await client.get(
        "/api/signage/player/playlist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) >= {"playlist_id", "name", "items", "resolved_at"}
    assert body["name"] == "match"
    assert len(body["items"]) == 2
    assert [it["position"] for it in body["items"]] == [1, 2]
    assert r.headers.get("etag"), r.headers
    assert r.headers.get("cache-control") == "no-cache"


async def test_playlist_returns_304_on_matching_etag(client, dsn):
    device_id = await _insert_device(dsn, status="online")
    await _seed_matched_playlist(dsn, device_id=device_id)
    token = mint_device_jwt(device_id)

    r1 = await client.get(
        "/api/signage/player/playlist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200, r1.text
    etag = r1.headers["etag"]
    assert etag

    r2 = await client.get(
        "/api/signage/player/playlist",
        headers={"Authorization": f"Bearer {token}", "If-None-Match": etag},
    )
    assert r2.status_code == 304, r2.text
    assert r2.content == b""
    # Server still echoes the ETag on 304.
    assert r2.headers.get("etag") == etag


async def test_playlist_does_not_touch_last_seen_at(client, dsn):
    """D-10: GET /playlist is pure read. Heartbeat owns presence."""
    device_id = await _insert_device(dsn, status="online", last_seen_at=None)
    token = mint_device_jwt(device_id)

    r = await client.get(
        "/api/signage/player/playlist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text

    row = await _fetch_device(dsn, device_id)
    assert row["last_seen_at"] is None, row


# --------------------------------------------------------------------------
# POST /api/signage/player/heartbeat
# --------------------------------------------------------------------------


async def test_heartbeat_requires_device_token(client, dsn):
    r = await client.post(
        "/api/signage/player/heartbeat",
        json={"current_item_id": None, "playlist_etag": None},
    )
    assert r.status_code == 401, r.text


async def test_heartbeat_returns_204_and_updates_device(client, dsn):
    device_id = await _insert_device(dsn, status="online", last_seen_at=None)
    item_id = uuid.uuid4()
    token = mint_device_jwt(device_id)

    r = await client.post(
        "/api/signage/player/heartbeat",
        json={"current_item_id": str(item_id), "playlist_etag": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204, r.text

    row = await _fetch_device(dsn, device_id)
    assert row["current_item_id"] == item_id
    assert row["current_playlist_etag"] == "x"
    assert row["last_seen_at"] is not None
    delta = (datetime.now(timezone.utc) - row["last_seen_at"]).total_seconds()
    assert 0 <= delta <= 10, delta


async def test_heartbeat_flips_offline_to_online(client, dsn):
    device_id = await _insert_device(dsn, status="offline")
    token = mint_device_jwt(device_id)

    r = await client.post(
        "/api/signage/player/heartbeat",
        json={"current_item_id": None, "playlist_etag": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204, r.text

    row = await _fetch_device(dsn, device_id)
    assert row["status"] == "online", row


async def test_heartbeat_accepts_null_payload(client, dsn):
    """A just-booted kiosk with no current item or cached etag must still heartbeat."""
    device_id = await _insert_device(dsn, status="online")
    token = mint_device_jwt(device_id)

    r = await client.post(
        "/api/signage/player/heartbeat",
        json={"current_item_id": None, "playlist_etag": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204, r.text
