"""Integration tests for the FAIR router (v1.63).

Covers the project + balloon lifecycle, server-side sequential numbering,
renumber-on-delete, the Directus file proxy, and the admin gate. The two
Directus helpers are monkeypatched so no real HTTP fires; a live Postgres is
required (skipped otherwise). Mirrors test_signage_pptx_upload.py.

SAFETY: only touches fair_* tables (new + empty on prod). Never run the full
suite against a database holding real data — see the pytest-wipes-prod-db note.
"""
from __future__ import annotations

import io
import os

import asyncpg
import pytest

from tests._auth import ADMIN_UUID, VIEWER_UUID, mint


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
        pytest.skip("POSTGRES_* not set — FAIR endpoint tests need a live DB")
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
        # fair_balloons cascades from fair_projects, but delete both explicitly.
        await conn.execute("DELETE FROM fair_balloons")
        await conn.execute("DELETE FROM fair_projects")
    finally:
        await conn.close()


@pytest.fixture
def _patched_directus(monkeypatch):
    """Stub the two fair_files helpers imported by the router."""
    async def _upload_stub(filename, content_type, body_stream):
        total = 0
        async for chunk in body_stream:
            total += len(chunk)
        return ("fake-directus-uuid", total)

    async def _fetch_stub(file_uuid):
        return (b"%PDF-1.4 fake", "application/pdf")

    import app.routers.fair as fair_mod

    monkeypatch.setattr(fair_mod, "upload_drawing_to_directus", _upload_stub)
    monkeypatch.setattr(fair_mod, "fetch_directus_asset", _fetch_stub)


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


async def _create_project(client) -> dict:
    files = {"file": ("teil-4711.pdf", io.BytesIO(b"%PDF-1.4 body"), "application/pdf")}
    r = await client.post(
        "/api/fair/projects", headers=_admin_headers(), files=files, data={"name": "Teil 4711"}
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _add_balloon(client, project_id: str, **over) -> dict:
    body = {
        "page_no": 1,
        "region_x": 0.10,
        "region_y": 0.20,
        "region_w": 0.05,
        "region_h": 0.03,
        "tail_x": 0.30,
        "tail_y": 0.40,
        "value_text": "Ø12,5",
        **over,
    }
    r = await client.post(
        f"/api/fair/projects/{project_id}/balloons",
        headers=_admin_headers(),
        json=body,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_project_and_balloon_lifecycle(client, _patched_directus):
    dsn = await _require_db()
    try:
        project = await _create_project(client)
        pid = project["id"]
        assert project["name"] == "Teil 4711"
        assert project["file_kind"] == "pdf"

        # Server assigns contiguous numbers.
        b1 = await _add_balloon(client, pid, value_text="Ø12,5")
        b2 = await _add_balloon(client, pid, value_text="M6")
        b3 = await _add_balloon(client, pid, value_text="R2,5")
        assert [b1["number"], b2["number"], b3["number"]] == [1, 2, 3]

        # Detail returns balloons ordered by number.
        r = await client.get(f"/api/fair/projects/{pid}", headers=_admin_headers())
        assert r.status_code == 200
        detail = r.json()
        assert [b["number"] for b in detail["balloons"]] == [1, 2, 3]

        # PATCH moves a bubble + edits its value.
        r = await client.patch(
            f"/api/fair/balloons/{b2['id']}",
            headers=_admin_headers(),
            json={"tail_x": 0.55, "value_text": "M6x1"},
        )
        assert r.status_code == 200
        patched = r.json()
        assert patched["tail_x"] == pytest.approx(0.55)
        assert patched["value_text"] == "M6x1"

        # DELETE balloon #1 → survivors renumber to 1..n contiguous.
        r = await client.delete(
            f"/api/fair/balloons/{b1['id']}", headers=_admin_headers()
        )
        assert r.status_code == 204
        r = await client.get(f"/api/fair/projects/{pid}", headers=_admin_headers())
        nums = sorted(b["number"] for b in r.json()["balloons"])
        assert nums == [1, 2]

        # File proxy returns the stubbed bytes + content-type.
        r = await client.get(
            f"/api/fair/projects/{pid}/file", headers=_admin_headers()
        )
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content == b"%PDF-1.4 fake"

        # Cascade delete.
        r = await client.delete(
            f"/api/fair/projects/{pid}", headers=_admin_headers()
        )
        assert r.status_code == 204
        r = await client.get(f"/api/fair/projects/{pid}", headers=_admin_headers())
        assert r.status_code == 404
    finally:
        await _cleanup(dsn)


async def test_viewer_cannot_create_project(client, _patched_directus):
    await _require_db()
    files = {"file": ("x.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}
    r = await client.post(
        "/api/fair/projects",
        headers={"Authorization": f"Bearer {mint(VIEWER_UUID)}"},
        files=files,
    )
    assert r.status_code == 403


async def test_unsupported_file_type_rejected(client, _patched_directus):
    await _require_db()
    files = {"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")}
    r = await client.post(
        "/api/fair/projects", headers=_admin_headers(), files=files
    )
    assert r.status_code == 422
