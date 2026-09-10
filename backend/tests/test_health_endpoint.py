"""Befund 14: /health verrät nichts über die Datenbank."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_health_ok(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_health_nennt_bei_ausfall_weder_host_noch_benutzer(client, monkeypatch):
    """Der Ausnahmetext einer asyncpg-Verbindung enthält DSN-Bestandteile.

    Die Route ist unauthentifiziert — sie darf davon nichts weitergeben.
    """
    from app import main as main_mod

    class _KaputterMotor:
        def connect(self):
            raise ConnectionError(
                "connection to server at \"db\" (172.18.0.2), port 5432 failed: "
                "FATAL: password authentication failed for user \"kpi\""
            )

    monkeypatch.setattr(main_mod, "engine", _KaputterMotor())

    r = await client.get("/health")
    assert r.status_code == 503
    text = r.text
    assert "kpi" not in text
    assert "5432" not in text
    assert "172.18" not in text
    assert r.json()["detail"] == "database unavailable"
