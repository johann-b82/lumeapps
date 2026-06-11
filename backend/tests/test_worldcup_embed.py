"""Endpoint tests for the public GET /api/worldcup/embed/today route.

Upstream is mocked via monkeypatch on worldcup_feed._fetch_upstream; the
worldcup settings columns are set directly on the app_settings row because
the autouse reset_settings fixture only resets DEFAULT_SETTINGS keys.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import update

from app.models import AppSettings
from app.security.fernet import encrypt_credential
from app.services import worldcup_feed as wcf


@pytest.fixture(autouse=True)
def fresh_cache():
    wcf.reset_cache()
    yield
    wcf.reset_cache()


def _raw_match_now():
    # Kickoff "now" so the match is always on today's Berlin date.
    utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": 1,
        "utcDate": utc,
        "status": "IN_PLAY",
        "minute": 37,
        "homeTeam": {"name": "Deutschland", "shortName": "Germany", "tla": "GER", "crest": None},
        "awayTeam": {"name": "Mexiko", "shortName": "Mexico", "tla": "MEX", "crest": None},
        "score": {"fullTime": {"home": 1, "away": 0}},
    }


async def _set_worldcup(api_key_enc, refresh=60):
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as s:
        await s.execute(
            update(AppSettings)
            .where(AppSettings.id == 1)
            .values(worldcup_api_key_enc=api_key_enc, worldcup_refresh_seconds=refresh)
        )
        await s.commit()


@pytest.mark.asyncio
async def test_not_configured_returns_empty_feed(client):
    await _set_worldcup(None)
    r = await client.get("/api/worldcup/embed/today")
    assert r.status_code == 200
    body = r.json()
    assert body["error"] == "not_configured"
    assert body["matches"] == []


@pytest.mark.asyncio
async def test_today_feed_unauthenticated(client, monkeypatch):
    await _set_worldcup(encrypt_credential("test-key"), refresh=120)
    seen = {}

    async def fake_fetch(api_key, date_from, date_to):
        seen["key"] = api_key
        return [_raw_match_now()]

    monkeypatch.setattr(wcf, "_fetch_upstream", fake_fetch)
    r = await client.get("/api/worldcup/embed/today")  # no auth header — public
    assert r.status_code == 200
    body = r.json()
    assert seen["key"] == "test-key", "decrypted key must reach upstream"
    assert body["refresh_seconds"] == 120
    assert body["matches"][0]["home"]["name"] == "Deutschland"
    assert body["matches"][0]["status"] == "IN_PLAY"
