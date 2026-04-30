"""Phase 62-01 backend calibration — integration tests (CAL-BE-01..05).

Covers:
  - CAL-BE-01: migration adds rotation/hdmi_mode/audio_enabled with D-07 defaults
  - CAL-BE-02: admin GET list + single include the three calibration fields
  - CAL-BE-03: PATCH /calibration partial update + 422 on invalid rotation + admin gate
  - CAL-BE-04: SSE calibration-changed fan-out (D-08 payload shape)
  - CAL-BE-05: device-auth GET /api/signage/player/calibration scoped to caller

DB-dependent (asyncpg). Skips cleanly when POSTGRES_* is unset.
"""
from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

from app.services import signage_broadcast
from app.services.signage_pairing import mint_device_jwt
from tests.test_directus_auth import (
    ADMIN_UUID,
    VIEWER_UUID,
    _mint as _mint_user_jwt,
)

pytestmark = pytest.mark.integration


# --------------------------------------------------------------------------
# DSN / skip helpers (mirrors test_signage_player_router.py)
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
        pytest.skip("POSTGRES_* not set — calibration tests need a live DB")
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
        await conn.execute("DELETE FROM signage_device_tag_map")
        await conn.execute("DELETE FROM signage_pairing_sessions")
        await conn.execute("DELETE FROM signage_devices")
        await conn.execute("DELETE FROM signage_device_tags")
    finally:
        await conn.close()


async def _insert_device(
    dsn: str,
    *,
    name: str = "pi-cal",
    rotation: int | None = None,
    hdmi_mode: str | None = None,
    audio_enabled: bool | None = None,
) -> uuid.UUID:
    """Insert a device row. If rotation/hdmi_mode/audio_enabled are None,
    rely on column defaults (tests CAL-BE-01 backfill semantics)."""
    device_id = uuid.uuid4()
    cols = ["id", "name", "status"]
    vals: list = [device_id, name, "offline"]
    placeholders = ["$1", "$2", "$3"]
    idx = 4
    if rotation is not None:
        cols.append("rotation")
        vals.append(rotation)
        placeholders.append(f"${idx}")
        idx += 1
    if hdmi_mode is not None:
        cols.append("hdmi_mode")
        vals.append(hdmi_mode)
        placeholders.append(f"${idx}")
        idx += 1
    if audio_enabled is not None:
        cols.append("audio_enabled")
        vals.append(audio_enabled)
        placeholders.append(f"${idx}")
        idx += 1
    sql = (
        f"INSERT INTO signage_devices ({', '.join(cols)}) "
        f"VALUES ({', '.join(placeholders)})"
    )
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(sql, *vals)
    finally:
        await conn.close()
    return device_id


# ---------------------------------------------------------------------------
# CAL-BE-01: migration + defaults
# ---------------------------------------------------------------------------


async def test_cal_be_01_migration_columns_exist_with_defaults(client):
    """CAL-BE-01: migration adds rotation/hdmi_mode/audio_enabled.

    Per D-07: existing rows backfilled with rotation=0, hdmi_mode=NULL,
    audio_enabled=false.
    """
    dsn = await _require_db()
    try:
        device_id = await _insert_device(dsn, name="cal-01-defaults")
        conn = await asyncpg.connect(dsn=dsn)
        try:
            row = await conn.fetchrow(
                "SELECT rotation, hdmi_mode, audio_enabled"
                " FROM signage_devices WHERE id = $1",
                device_id,
            )
        finally:
            await conn.close()
        assert row is not None
        assert row["rotation"] == 0, "D-07: default rotation backfill"
        assert row["hdmi_mode"] is None, "D-07: hdmi_mode NULL default"
        assert row["audio_enabled"] is False, "D-07: audio_enabled false default"
    finally:
        await _cleanup(dsn)


async def test_cal_be_01_rotation_check_constraint_rejects_45(client):
    """CAL-BE-01: DB-level CHECK constraint rejects non-{0,90,180,270}."""
    dsn = await _require_db()
    try:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            did = uuid.uuid4()
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO signage_devices (id, name, status, rotation)"
                    " VALUES ($1, $2, 'offline', 45)",
                    did,
                    "bad-rot",
                )
        finally:
            await conn.close()
    finally:
        await _cleanup(dsn)


# ---------------------------------------------------------------------------
# CAL-BE-02: admin GET returns calibration fields
# ---------------------------------------------------------------------------


async def test_cal_be_02_admin_get_list_includes_calibration(client):
    dsn = await _require_db()
    try:
        await _insert_device(
            dsn,
            name="cal-02-list",
            rotation=90,
            hdmi_mode="1920x1080@60",
            audio_enabled=True,
        )
        token = _mint_user_jwt(ADMIN_UUID)
        r = await client.get(
            "/api/signage/devices",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        rows = r.json()
        assert len(rows) >= 1
        target = next(d for d in rows if d["name"] == "cal-02-list")
        assert target["rotation"] == 90
        assert target["hdmi_mode"] == "1920x1080@60"
        assert target["audio_enabled"] is True
    finally:
        await _cleanup(dsn)


async def test_cal_be_02_admin_get_single_includes_calibration(client):
    dsn = await _require_db()
    try:
        did = await _insert_device(
            dsn,
            name="cal-02-single",
            rotation=180,
            hdmi_mode=None,
            audio_enabled=False,
        )
        token = _mint_user_jwt(ADMIN_UUID)
        r = await client.get(
            f"/api/signage/devices/{did}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["rotation"] == 180
        assert body["hdmi_mode"] is None
        assert body["audio_enabled"] is False
    finally:
        await _cleanup(dsn)


# ---------------------------------------------------------------------------
# CAL-BE-03: PATCH /calibration — partial, 422, admin gate
# ---------------------------------------------------------------------------


async def test_cal_be_03_patch_partial_updates_only_provided_fields(client):
    dsn = await _require_db()
    try:
        did = await _insert_device(
            dsn,
            name="cal-03-partial",
            rotation=0,
            hdmi_mode="1024x768@60",
            audio_enabled=True,
        )
        token = _mint_user_jwt(ADMIN_UUID)
        r = await client.patch(
            f"/api/signage/devices/{did}/calibration",
            json={"rotation": 90},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["rotation"] == 90
        # Untouched:
        assert body["hdmi_mode"] == "1024x768@60"
        assert body["audio_enabled"] is True
    finally:
        await _cleanup(dsn)


async def test_cal_be_03_patch_rejects_invalid_rotation(client):
    dsn = await _require_db()
    try:
        did = await _insert_device(dsn, name="cal-03-bad-rot")
        token = _mint_user_jwt(ADMIN_UUID)
        r = await client.patch(
            f"/api/signage/devices/{did}/calibration",
            json={"rotation": 45},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422, r.text
    finally:
        await _cleanup(dsn)


async def test_cal_be_03_patch_requires_admin(client):
    dsn = await _require_db()
    try:
        did = await _insert_device(dsn, name="cal-03-admin-gate")
        # Viewer gets 403
        viewer = _mint_user_jwt(VIEWER_UUID)
        r = await client.patch(
            f"/api/signage/devices/{did}/calibration",
            json={"rotation": 90},
            headers={"Authorization": f"Bearer {viewer}"},
        )
        assert r.status_code == 403, r.text
        # No JWT gets 401
        r = await client.patch(
            f"/api/signage/devices/{did}/calibration",
            json={"rotation": 90},
        )
        assert r.status_code == 401, r.text
    finally:
        await _cleanup(dsn)


async def test_cal_be_03_patch_404_on_unknown_device(client):
    await _require_db()
    token = _mint_user_jwt(ADMIN_UUID)
    r = await client.patch(
        f"/api/signage/devices/{uuid.uuid4()}/calibration",
        json={"rotation": 90},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# CAL-BE-04: SSE calibration-changed fan-out
# ---------------------------------------------------------------------------


async def test_cal_be_04_patch_emits_calibration_changed_sse(client, monkeypatch):
    """D-08: payload shape is {event: 'calibration-changed', device_id: <uuid-str>}."""
    dsn = await _require_db()
    try:
        did = await _insert_device(dsn, name="cal-04-sse")

        captured: list[tuple] = []

        def spy(dev_id, payload):
            captured.append((dev_id, payload))

        monkeypatch.setattr(signage_broadcast, "notify_device", spy)
        # The calibration PATCH imports notify_device via the module path; patch
        # the reference the router actually uses.
        import app.routers.signage_admin.devices as dev_mod
        monkeypatch.setattr(
            dev_mod.signage_broadcast, "notify_device", spy
        )

        token = _mint_user_jwt(ADMIN_UUID)
        r = await client.patch(
            f"/api/signage/devices/{did}/calibration",
            json={"rotation": 270, "audio_enabled": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text

        # Find the calibration-changed event (there may also be unrelated events
        # from other code paths — we only assert ours fires).
        cal_events = [
            (d, p) for (d, p) in captured
            if isinstance(p, dict) and p.get("event") == "calibration-changed"
        ]
        assert len(cal_events) == 1, (
            f"expected exactly one calibration-changed event, got {captured}"
        )
        evt_dev_id, evt_payload = cal_events[0]
        assert evt_dev_id == did
        assert evt_payload == {
            "event": "calibration-changed",
            "device_id": str(did),
        }
    finally:
        await _cleanup(dsn)


# ---------------------------------------------------------------------------
# CAL-BE-05: device-auth player GET /calibration
# ---------------------------------------------------------------------------


async def test_cal_be_05_player_get_calibration_returns_caller_state(client):
    dsn = await _require_db()
    try:
        did = await _insert_device(
            dsn,
            name="cal-05-self",
            rotation=90,
            hdmi_mode="1280x720@60",
            audio_enabled=True,
        )
        token = mint_device_jwt(did)
        r = await client.get(
            "/api/signage/player/calibration",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body == {
            "rotation": 90,
            "hdmi_mode": "1280x720@60",
            "audio_enabled": True,
        }
    finally:
        await _cleanup(dsn)


async def test_cal_be_05_player_get_calibration_scoped_to_caller(client):
    """Device A's JWT returns device A's calibration; device B's JWT returns B's."""
    dsn = await _require_db()
    try:
        did_a = await _insert_device(
            dsn,
            name="cal-05-A",
            rotation=0,
            hdmi_mode=None,
            audio_enabled=False,
        )
        did_b = await _insert_device(
            dsn,
            name="cal-05-B",
            rotation=180,
            hdmi_mode="1920x1080@60",
            audio_enabled=True,
        )
        token_a = mint_device_jwt(did_a)
        token_b = mint_device_jwt(did_b)

        ra = await client.get(
            "/api/signage/player/calibration",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        rb = await client.get(
            "/api/signage/player/calibration",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert ra.status_code == 200
        assert rb.status_code == 200
        assert ra.json()["rotation"] == 0
        assert ra.json()["audio_enabled"] is False
        assert rb.json()["rotation"] == 180
        assert rb.json()["hdmi_mode"] == "1920x1080@60"
        assert rb.json()["audio_enabled"] is True
    finally:
        await _cleanup(dsn)


async def test_cal_be_05_player_get_calibration_requires_device_auth(client):
    await _require_db()
    # No JWT
    r = await client.get("/api/signage/player/calibration")
    assert r.status_code == 401, r.text
    # User JWT should fail (device-auth router gate, not admin gate)
    token = _mint_user_jwt(ADMIN_UUID)
    r = await client.get(
        "/api/signage/player/calibration",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401, r.text
