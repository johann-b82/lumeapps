"""Integration tests for POST /api/signage/media/pptx (SGN-BE-07, Phase 44 Plan 03).

Covers D-08, D-10, D-11, D-13:
  - Happy path (canonical PPTX MIME) -> 201, row inserted pending, convert_pptx scheduled.
  - Extension-fallback path (application/octet-stream + .pptx filename) -> 201.
  - Rejected MIME (image/png + .png) -> 400, no row, no scheduling.
  - 413 path (uploader raises HTTPException(413)) -> 413, no row, no scheduling.

Mirrors the fixture / seeding pattern in test_signage_admin_router.py.
"""
from __future__ import annotations

import io
import os
import uuid
from unittest.mock import MagicMock

import asyncpg
import pytest

from tests.test_directus_auth import _mint, ADMIN_UUID


PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


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
        pytest.skip("POSTGRES_* not set — upload endpoint tests need a live DB")
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
        await conn.execute("DELETE FROM signage_playlist_tag_map")
        await conn.execute("DELETE FROM signage_device_tag_map")
        await conn.execute("DELETE FROM signage_playlist_items")
        await conn.execute("DELETE FROM signage_playlists")
        await conn.execute("DELETE FROM signage_media")
    finally:
        await conn.close()


async def _count_media(dsn: str) -> int:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        return await conn.fetchval("SELECT COUNT(*) FROM signage_media")
    finally:
        await conn.close()


@pytest.fixture
def _patched_helpers(monkeypatch):
    """Stub the two helpers imported by media.py so no real HTTP/subprocess fires.

    Returns (upload_stub, convert_mock) to let tests assert call counts.
    """
    # convert_pptx is scheduled via BackgroundTasks — replace with a MagicMock so
    # we can assert it was scheduled (and prevent it from actually running).
    convert_mock = MagicMock()

    captured_bytes: dict[str, int] = {"total": 0}

    async def _upload_stub(filename, content_type, body_stream):
        # Drain the stream so the UploadFile is fully consumed (mirrors real helper).
        total = 0
        async for chunk in body_stream:
            total += len(chunk)
        captured_bytes["total"] = total
        return ("fake-directus-uuid", total)

    from app.routers.signage_admin import media as media_mod

    monkeypatch.setattr(media_mod, "upload_pptx_to_directus", _upload_stub)
    monkeypatch.setattr(media_mod, "convert_pptx", convert_mock)

    return _upload_stub, convert_mock, captured_bytes


# ---------------------------------------------------------------------------
# Happy path — canonical PPTX MIME
# ---------------------------------------------------------------------------


async def test_upload_pptx_happy_path_canonical_mime(client, _patched_helpers):
    dsn = await _require_db()
    _upload, convert_mock, captured = _patched_helpers
    try:
        token = _mint(ADMIN_UUID)
        body = b"fakepptxbytes" * 10  # 130 bytes
        files = {"file": ("deck.pptx", io.BytesIO(body), PPTX_MIME)}
        data = {"title": "Quarterly Review"}
        r = await client.post(
            "/api/signage/media/pptx",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert r.status_code == 201, r.text
        payload = r.json()
        assert payload["kind"] == "pptx"
        assert payload["title"] == "Quarterly Review"
        assert payload["conversion_status"] == "pending"
        assert payload["slide_paths"] is None
        assert payload["uri"] == "fake-directus-uuid"
        assert payload["size_bytes"] == len(body)
        assert payload["mime_type"] == PPTX_MIME
        assert captured["total"] == len(body)

        # Row is persisted.
        assert await _count_media(dsn) == 1

        # BackgroundTask scheduled convert_pptx with the new row id exactly once.
        assert convert_mock.call_count == 1
        called_id = convert_mock.call_args.args[0]
        assert uuid.UUID(str(called_id))
    finally:
        await _cleanup(dsn)


# ---------------------------------------------------------------------------
# Extension fallback — browsers often send application/octet-stream for .pptx
# ---------------------------------------------------------------------------


async def test_upload_pptx_accepts_octet_stream_with_pptx_extension(
    client, _patched_helpers
):
    dsn = await _require_db()
    _upload, convert_mock, _captured = _patched_helpers
    try:
        token = _mint(ADMIN_UUID)
        body = b"xxxxxxxxx"
        files = {"file": ("deck.pptx", io.BytesIO(body), "application/octet-stream")}
        data = {"title": "Octet Stream Deck"}
        r = await client.post(
            "/api/signage/media/pptx",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert r.status_code == 201, r.text
        assert r.json()["conversion_status"] == "pending"
        assert convert_mock.call_count == 1
    finally:
        await _cleanup(dsn)


# ---------------------------------------------------------------------------
# Rejected MIME + extension
# ---------------------------------------------------------------------------


async def test_upload_pptx_rejects_non_pptx(client, _patched_helpers):
    dsn = await _require_db()
    _upload, convert_mock, _captured = _patched_helpers
    try:
        token = _mint(ADMIN_UUID)
        body = b"\x89PNGfakefakefake"
        files = {"file": ("foo.png", io.BytesIO(body), "image/png")}
        data = {"title": "Not a PPTX"}
        r = await client.post(
            "/api/signage/media/pptx",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert r.status_code == 400, r.text
        # No row inserted, no task scheduled.
        assert await _count_media(dsn) == 0
        assert convert_mock.call_count == 0
    finally:
        await _cleanup(dsn)


# ---------------------------------------------------------------------------
# 50MB cap -> 413 (helper raises HTTPException(413))
# ---------------------------------------------------------------------------


async def test_upload_pptx_returns_413_when_uploader_raises(client, monkeypatch):
    dsn = await _require_db()
    try:
        from fastapi import HTTPException
        from app.routers.signage_admin import media as media_mod

        async def _raising_upload(filename, content_type, body_stream):
            # Drain the stream to mirror the real helper's cap-while-streaming shape.
            async for _chunk in body_stream:
                pass
            raise HTTPException(status_code=413, detail="pptx upload exceeds 50MB cap")

        convert_mock = MagicMock()
        monkeypatch.setattr(media_mod, "upload_pptx_to_directus", _raising_upload)
        monkeypatch.setattr(media_mod, "convert_pptx", convert_mock)

        token = _mint(ADMIN_UUID)
        body = b"a" * 1024  # small body; the helper is the one raising 413.
        files = {"file": ("huge.pptx", io.BytesIO(body), PPTX_MIME)}
        data = {"title": "Too Big"}
        r = await client.post(
            "/api/signage/media/pptx",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert r.status_code == 413, r.text
        assert await _count_media(dsn) == 0
        assert convert_mock.call_count == 0
    finally:
        await _cleanup(dsn)
