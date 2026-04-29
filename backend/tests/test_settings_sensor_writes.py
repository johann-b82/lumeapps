"""Phase 40-01 — PUT /api/settings sensor interval + threshold writes.

Covers SEN-ADM-04 (interval reschedule) + SEN-ADM-05 (threshold persistence).

Uses the repo's standard async harness (httpx.AsyncClient + LifespanManager via
conftest `client` fixture) — NOT starlette.TestClient (repo pattern per
tests/test_sensors_admin_gate.py + conftest.py comments).
"""
from __future__ import annotations

import pytest

from app.defaults import DEFAULT_SETTINGS
from tests.test_directus_auth import _mint, ADMIN_UUID

pytestmark = pytest.mark.asyncio


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_mint(ADMIN_UUID)}"}


def _base_payload() -> dict:
    # PUT /api/settings requires the full brand block — only the new 5 sensor
    # fields are optional. We supply the canonical defaults for everything else.
    return dict(DEFAULT_SETTINGS)


async def test_put_settings_interval_reschedules(client, monkeypatch):
    """SEN-ADM-04: PUT with sensor_poll_interval_s=30 reschedules the poll job."""
    calls: list[int] = []

    def fake_reschedule(new_interval_s: int) -> None:
        calls.append(new_interval_s)

    # settings.py does `from app.scheduler import reschedule_sensor_poll`
    # inside the handler — patch at the source module so the import picks up
    # the fake regardless of when the patch is applied.
    monkeypatch.setattr("app.scheduler.reschedule_sensor_poll", fake_reschedule)

    payload = {**_base_payload(), "sensor_poll_interval_s": 30}
    r = await client.put("/api/settings", json=payload, headers=_admin_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sensor_poll_interval_s"] == 30
    assert calls == [30], f"reschedule_sensor_poll expected once(30), got {calls}"


async def test_put_settings_interval_bounds(client):
    """SEN-ADM-04: interval out of 5..86400 is rejected by Pydantic (422)."""
    headers = _admin_headers()
    for bad in (4, 86401):
        r = await client.put(
            "/api/settings",
            json={**_base_payload(), "sensor_poll_interval_s": bad},
            headers=headers,
        )
        assert r.status_code == 422, (
            f"expected 422 for sensor_poll_interval_s={bad}, got {r.status_code} {r.text}"
        )


async def test_put_settings_threshold_write(client):
    """SEN-ADM-05: temperature min/max persisted; GET round-trips the values."""
    payload = {
        **_base_payload(),
        "sensor_temperature_min": "18.5",
        "sensor_temperature_max": "25.0",
        "sensor_humidity_min": "30.0",
        "sensor_humidity_max": "70.0",
    }
    r = await client.put("/api/settings", json=payload, headers=_admin_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    # Decimal serializes as string on read — compare by Decimal coercion.
    from decimal import Decimal
    assert Decimal(body["sensor_temperature_min"]) == Decimal("18.5")
    assert Decimal(body["sensor_temperature_max"]) == Decimal("25.0")
    assert Decimal(body["sensor_humidity_min"]) == Decimal("30.0")
    assert Decimal(body["sensor_humidity_max"]) == Decimal("70.0")

    # GET should reflect the same values.
    r2 = await client.get("/api/settings", headers=_admin_headers())
    assert r2.status_code == 200, r2.text
    g = r2.json()
    assert Decimal(g["sensor_temperature_min"]) == Decimal("18.5")
    assert Decimal(g["sensor_humidity_max"]) == Decimal("70.0")
