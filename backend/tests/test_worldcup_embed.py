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


@pytest.mark.asyncio
async def test_standings_endpoint_unauthenticated(client, monkeypatch):
    await _set_worldcup(encrypt_credential("test-key"))

    async def fake(api_key):
        return [{"type": "TOTAL", "group": "GROUP_A", "table": [
            {"position": 1,
             "team": {"name": "Mexico", "shortName": "Mexico", "tla": "MEX", "crest": None},
             "playedGames": 3, "won": 3, "draw": 0, "lost": 0,
             "points": 9, "goalsFor": 7, "goalsAgainst": 2, "goalDifference": 5}]}]

    monkeypatch.setattr(wcf, "_fetch_standings", fake)
    r = await client.get("/api/worldcup/embed/standings")
    assert r.status_code == 200
    assert r.json()["groups"][0]["group"] == "Group A"


@pytest.mark.asyncio
async def test_matches_endpoint_not_configured(client):
    await _set_worldcup(None)
    r = await client.get("/api/worldcup/embed/matches")
    assert r.status_code == 200
    assert r.json()["error"] == "not_configured"


@pytest.mark.asyncio
async def test_knockout_and_scorers_endpoints(client, monkeypatch):
    await _set_worldcup(encrypt_credential("test-key"))

    async def fake_matches(api_key):
        return [{"id": 1, "utcDate": "2026-07-05T19:00:00Z", "status": "TIMED",
                 "stage": "FINAL", "minute": None,
                 "homeTeam": {"name": "A", "tla": "AAA", "crest": None},
                 "awayTeam": {"name": "B", "tla": "BBB", "crest": None},
                 "score": {"fullTime": {"home": None, "away": None}}}]

    async def fake_scorers(api_key):
        return [{"player": {"name": "X"}, "team": {"name": "Y"}, "goals": 3}]

    monkeypatch.setattr(wcf, "_fetch_all_matches", fake_matches)
    monkeypatch.setattr(wcf, "_fetch_scorers", fake_scorers)
    rk = await client.get("/api/worldcup/embed/knockout")
    rs = await client.get("/api/worldcup/embed/scorers")
    assert rk.json()["stages"][0]["stage"] == "FINAL"
    assert rs.json()["scorers"][0]["rank"] == 1
