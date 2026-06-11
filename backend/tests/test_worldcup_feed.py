"""Unit tests for app/services/worldcup_feed.py — no DB, no network.

Upstream and clock are injected via monkeypatch on module globals
(`_fetch_upstream`, `_utcnow`); `reset_cache()` isolates tests.
"""
from datetime import date, datetime, timezone

import httpx
import pytest

from app.services import worldcup_feed as wcf


def _raw(id=1, utc="2026-06-11T19:00:00Z", status="IN_PLAY", home=1, away=0, minute=37):
    return {
        "id": id,
        "utcDate": utc,
        "status": status,
        "minute": minute,
        "homeTeam": {
            "name": "Deutschland", "shortName": "Germany", "tla": "GER",
            "crest": "https://crests.football-data.org/759.png",
        },
        "awayTeam": {
            "name": "Mexiko", "shortName": "Mexico", "tla": "MEX",
            "crest": "https://crests.football-data.org/769.png",
        },
        "score": {"fullTime": {"home": home, "away": away}},
    }


# --- build_feed (pure) ----------------------------------------------------

def test_build_feed_maps_today():
    feed = wcf.build_feed([_raw()], "Europe/Berlin", date(2026, 6, 11), 60)
    assert len(feed.matches) == 1
    m = feed.matches[0]
    assert m.home.name == "Deutschland"
    assert m.away.short_name == "Mexico"
    assert (m.score_home, m.score_away) == (1, 0)
    assert m.status == "IN_PLAY"
    assert m.minute == 37
    assert feed.next_matchday is None


def test_build_feed_berlin_date_boundary():
    # 23:00 UTC on the 11th is 01:00 on the 12th in Berlin (CEST) — not today.
    feed = wcf.build_feed(
        [_raw(utc="2026-06-11T23:00:00Z")], "Europe/Berlin", date(2026, 6, 11), 60
    )
    assert feed.matches == []
    assert feed.next_matchday == date(2026, 6, 12)
    assert len(feed.next_matches) == 1


def test_build_feed_next_matchday_only_when_today_empty():
    raws = [_raw(id=1), _raw(id=2, utc="2026-06-13T15:00:00Z")]
    feed = wcf.build_feed(raws, "Europe/Berlin", date(2026, 6, 11), 60)
    assert [m.id for m in feed.matches] == [1]
    assert feed.next_matchday is None


def test_build_feed_sorts_today_by_kickoff():
    raws = [_raw(id=2, utc="2026-06-11T19:00:00Z"), _raw(id=1, utc="2026-06-11T13:00:00Z")]
    feed = wcf.build_feed(raws, "Europe/Berlin", date(2026, 6, 11), 60)
    assert [m.id for m in feed.matches] == [1, 2]


def test_map_match_missing_score_and_minute():
    raw = _raw(status="TIMED")
    raw["score"] = {"fullTime": {"home": None, "away": None}}
    del raw["minute"]
    m = wcf.map_match(raw)
    assert m.score_home is None and m.score_away is None and m.minute is None


# --- get_feed (cache + stale) ----------------------------------------------

T0 = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_cache_serves_within_ttl(monkeypatch):
    wcf.reset_cache()
    calls = []

    async def fake_fetch(api_key, date_from, date_to):
        calls.append(api_key)
        return [_raw()]

    monkeypatch.setattr(wcf, "_fetch_upstream", fake_fetch)
    monkeypatch.setattr(wcf, "_utcnow", lambda: T0)
    f1 = await wcf.get_feed("k", 60, "Europe/Berlin")
    monkeypatch.setattr(wcf, "_utcnow", lambda: T0.replace(second=30))
    f2 = await wcf.get_feed("k", 60, "Europe/Berlin")
    assert calls == ["k"]  # second call served from cache
    assert f1.matches and f2.matches
    assert f2.stale_since is None


@pytest.mark.asyncio
async def test_cache_refetches_after_ttl(monkeypatch):
    wcf.reset_cache()
    calls = []

    async def fake_fetch(api_key, date_from, date_to):
        calls.append(1)
        return [_raw()]

    monkeypatch.setattr(wcf, "_fetch_upstream", fake_fetch)
    monkeypatch.setattr(wcf, "_utcnow", lambda: T0)
    await wcf.get_feed("k", 60, "Europe/Berlin")
    monkeypatch.setattr(wcf, "_utcnow", lambda: T0.replace(minute=2))
    await wcf.get_feed("k", 60, "Europe/Berlin")
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_stale_served_on_upstream_failure(monkeypatch):
    wcf.reset_cache()
    state = {"fail": False}

    async def fake_fetch(api_key, date_from, date_to):
        if state["fail"]:
            raise httpx.ConnectError("boom")
        return [_raw()]

    monkeypatch.setattr(wcf, "_fetch_upstream", fake_fetch)
    monkeypatch.setattr(wcf, "_utcnow", lambda: T0)
    f1 = await wcf.get_feed("k", 60, "Europe/Berlin")
    assert f1.stale_since is None

    state["fail"] = True
    monkeypatch.setattr(wcf, "_utcnow", lambda: T0.replace(minute=2))
    f2 = await wcf.get_feed("k", 60, "Europe/Berlin")
    assert f2.matches, "stale data must still be served"
    assert f2.stale_since == T0
    assert f2.error is None


@pytest.mark.asyncio
async def test_error_flag_when_never_fetched(monkeypatch):
    wcf.reset_cache()

    async def fake_fetch(api_key, date_from, date_to):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(wcf, "_fetch_upstream", fake_fetch)
    f = await wcf.get_feed("k", 60, "Europe/Berlin")
    assert f.matches == []
    assert f.error == "upstream_unavailable"
