"""Admin device remote commands — POST /api/signage/devices/{id}/{reload,reboot}.

Covers:
  - reload/reboot push ``{event, device_id}`` onto the device's player SSE
    fan-out and answer 202 with ``delivered`` = live subscriber count
  - ``delivered`` is 0 (still 202) when nobody is connected — fire-and-forget
  - 404 for an unknown device
  - viewer is rejected by the package-level admin gate (403)

DB-dependent (asyncpg). Skips cleanly when POSTGRES_* is unset.
"""
from __future__ import annotations

import uuid

import pytest

from app.services import signage_broadcast
from tests.test_directus_auth import (
    ADMIN_UUID,
    VIEWER_UUID,
)
from tests.test_directus_auth import (
    _mint as _mint_user_jwt,
)
from tests.test_signage_calibration import _insert_device, _require_db

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("command", ["reload", "reboot"])
async def test_command_fans_out_to_subscribers(client, command):
    dsn = await _require_db()
    did = await _insert_device(dsn, name=f"cmd-{command}")
    sidecar_q = signage_broadcast.subscribe(did)
    browser_q = signage_broadcast.subscribe(did)
    try:
        token = _mint_user_jwt(ADMIN_UUID)
        r = await client.post(
            f"/api/signage/devices/{did}/{command}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 202, r.text
        assert r.json() == {
            "event": command,
            "device_id": str(did),
            "delivered": 2,
        }
        expected = {"event": command, "device_id": str(did)}
        assert sidecar_q.get_nowait() == expected
        assert browser_q.get_nowait() == expected
    finally:
        signage_broadcast.unsubscribe(did, sidecar_q)
        signage_broadcast.unsubscribe(did, browser_q)


async def test_command_without_subscribers_reports_zero(client):
    dsn = await _require_db()
    did = await _insert_device(dsn, name="cmd-nobody")
    token = _mint_user_jwt(ADMIN_UUID)
    r = await client.post(
        f"/api/signage/devices/{did}/reload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 202, r.text
    assert r.json()["delivered"] == 0


async def test_command_unknown_device_404(client):
    await _require_db()
    token = _mint_user_jwt(ADMIN_UUID)
    r = await client.post(
        f"/api/signage/devices/{uuid.uuid4()}/reboot",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


async def test_command_viewer_forbidden(client):
    dsn = await _require_db()
    did = await _insert_device(dsn, name="cmd-viewer")
    token = _mint_user_jwt(VIEWER_UUID)
    r = await client.post(
        f"/api/signage/devices/{did}/reboot",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
