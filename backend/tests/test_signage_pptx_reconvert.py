"""Integration tests for POST /api/signage/media/{id}/reconvert (SGN-BE-07, Phase 44 Plan 03).

Covers D-12:
  - 404 when id not found.
  - 409 when kind != 'pptx'.
  - 409 when conversion_status == 'processing'.
  - 202 happy path from 'failed' -> pending; slide_paths/error/started_at all cleared,
    delete_slides_dir called with media_id, convert_pptx scheduled.
  - 202 happy path from 'done' also resets cleanly.

Mirrors the fixture pattern in test_signage_admin_router.py + test_signage_pptx_upload.py.
"""
from __future__ import annotations

import json
import os
import uuid
from unittest.mock import MagicMock

import asyncpg
import pytest

from tests.test_directus_auth import _mint, ADMIN_UUID


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
        pytest.skip("POSTGRES_* not set — reconvert endpoint tests need a live DB")
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


async def _insert_pptx_media(
    dsn: str,
    *,
    title: str = "deck",
    status: str | None = "failed",
    error: str | None = "soffice_failed",
    slide_paths: list | None = None,
) -> uuid.UUID:
    mid = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            """
            INSERT INTO signage_media
                (id, kind, title, uri, conversion_status, conversion_error, slide_paths)
            VALUES ($1, 'pptx', $2, $3, $4, $5, $6)
            """,
            mid,
            title,
            "directus-file-uuid",
            status,
            error,
            json.dumps(slide_paths) if slide_paths is not None else None,
        )
    finally:
        await conn.close()
    return mid


async def _insert_image_media(dsn: str) -> uuid.UUID:
    mid = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_media (id, kind, title, uri) VALUES ($1, 'image', 'img', 'https://x/y.png')",
            mid,
        )
    finally:
        await conn.close()
    return mid


async def _fetch_media_row(dsn: str, mid: uuid.UUID):
    conn = await asyncpg.connect(dsn=dsn)
    try:
        row = await conn.fetchrow(
            "SELECT conversion_status, slide_paths, conversion_error, conversion_started_at "
            "FROM signage_media WHERE id = $1",
            mid,
        )
    finally:
        await conn.close()
    # asyncpg returns JSONB as raw text — decode so `None` / list comparisons work.
    slide_paths_raw = row["slide_paths"]
    slide_paths = json.loads(slide_paths_raw) if slide_paths_raw is not None else None
    return {
        "conversion_status": row["conversion_status"],
        "slide_paths": slide_paths,
        "conversion_error": row["conversion_error"],
        "conversion_started_at": row["conversion_started_at"],
    }


@pytest.fixture
def _patched_helpers(monkeypatch):
    """Mock delete_slides_dir + convert_pptx in the router module's namespace."""
    from app.routers.signage_admin import media as media_mod

    delete_mock = MagicMock()
    convert_mock = MagicMock()
    monkeypatch.setattr(media_mod, "delete_slides_dir", delete_mock)
    monkeypatch.setattr(media_mod, "convert_pptx", convert_mock)
    return delete_mock, convert_mock


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


async def test_reconvert_404_when_not_found(client, _patched_helpers):
    dsn = await _require_db()
    delete_mock, convert_mock = _patched_helpers
    try:
        token = _mint(ADMIN_UUID)
        r = await client.post(
            f"/api/signage/media/{uuid.uuid4()}/reconvert",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404, r.text
        assert delete_mock.call_count == 0
        assert convert_mock.call_count == 0
    finally:
        await _cleanup(dsn)


async def test_reconvert_409_when_kind_not_pptx(client, _patched_helpers):
    dsn = await _require_db()
    delete_mock, convert_mock = _patched_helpers
    try:
        token = _mint(ADMIN_UUID)
        mid = await _insert_image_media(dsn)
        r = await client.post(
            f"/api/signage/media/{mid}/reconvert",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == "media is not a PPTX"
        assert delete_mock.call_count == 0
        assert convert_mock.call_count == 0
    finally:
        await _cleanup(dsn)


async def test_reconvert_409_when_already_processing(client, _patched_helpers):
    dsn = await _require_db()
    delete_mock, convert_mock = _patched_helpers
    try:
        token = _mint(ADMIN_UUID)
        mid = await _insert_pptx_media(
            dsn, status="processing", error=None, slide_paths=None
        )
        r = await client.post(
            f"/api/signage/media/{mid}/reconvert",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == "conversion already in progress"
        assert delete_mock.call_count == 0
        assert convert_mock.call_count == 0
    finally:
        await _cleanup(dsn)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


async def test_reconvert_202_from_failed_resets_row(client, _patched_helpers):
    dsn = await _require_db()
    delete_mock, convert_mock = _patched_helpers
    try:
        token = _mint(ADMIN_UUID)
        mid = await _insert_pptx_media(
            dsn,
            status="failed",
            error="soffice_failed",
            slide_paths=["slides/x/slide-001.png"],
        )
        r = await client.post(
            f"/api/signage/media/{mid}/reconvert",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 202, r.text
        body = r.json()
        assert body["conversion_status"] == "pending"
        assert body["slide_paths"] is None
        assert body["conversion_error"] is None
        assert body["conversion_started_at"] is None

        row = await _fetch_media_row(dsn, mid)
        assert row["conversion_status"] == "pending"
        assert row["slide_paths"] is None
        assert row["conversion_error"] is None
        assert row["conversion_started_at"] is None

        # delete_slides_dir called exactly once with the media_id (UUID).
        assert delete_mock.call_count == 1
        assert delete_mock.call_args.args[0] == mid
        # convert_pptx scheduled exactly once with the same media_id.
        assert convert_mock.call_count == 1
        assert convert_mock.call_args.args[0] == mid
    finally:
        await _cleanup(dsn)


async def test_reconvert_202_from_done_also_resets(client, _patched_helpers):
    dsn = await _require_db()
    delete_mock, convert_mock = _patched_helpers
    try:
        token = _mint(ADMIN_UUID)
        mid = await _insert_pptx_media(
            dsn,
            status="done",
            error=None,
            slide_paths=["slides/x/slide-001.png", "slides/x/slide-002.png"],
        )
        r = await client.post(
            f"/api/signage/media/{mid}/reconvert",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 202, r.text
        row = await _fetch_media_row(dsn, mid)
        assert row["conversion_status"] == "pending"
        assert row["slide_paths"] is None
        assert delete_mock.call_count == 1
        assert convert_mock.call_count == 1
    finally:
        await _cleanup(dsn)
