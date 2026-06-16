"""Unit tests for the extra World Cup feeds (standings, matches window,
knockout, scorers) — no DB, no network. Upstream fetchers and the clock are
monkeypatched on module globals; reset_cache() isolates tests."""
from datetime import date, datetime, timezone

import httpx
import pytest

from app.services import worldcup_feed as wcf


@pytest.fixture(autouse=True)
def fresh_cache():
    wcf.reset_cache()
    yield
    wcf.reset_cache()


def _raw_group(group="GROUP_A", tla="MEX"):
    return {
        "stage": "GROUP_STAGE",
        "type": "TOTAL",
        "group": group,
        "table": [
            {
                "position": 1,
                "team": {"name": "Mexico", "shortName": "Mexico", "tla": tla,
                         "crest": "https://crests.football-data.org/mex.png"},
                "playedGames": 3, "won": 3, "draw": 0, "lost": 0,
                "points": 9, "goalsFor": 7, "goalsAgainst": 2, "goalDifference": 5,
            }
        ],
    }


def test_build_standings_maps_groups_and_skips_non_total():
    raw = [_raw_group(), {"type": "HOME", "group": "GROUP_A", "table": []}]
    feed = wcf.build_standings(raw, 60)
    assert [g.group for g in feed.groups] == ["Group A"]
    row = feed.groups[0].table[0]
    assert row.position == 1
    assert row.team.name == "Mexico"
    assert row.team.crest.endswith("mex.png")
    assert (row.played, row.won, row.draw, row.lost) == (3, 3, 0, 0)
    assert row.goal_difference == 5
    assert row.points == 9


def _raw_match(id, utc, status="FINISHED", home=2, away=1, stage="GROUP_STAGE"):
    return {
        "id": id, "utcDate": utc, "status": status, "minute": None, "stage": stage,
        "homeTeam": {"name": "A", "shortName": "A", "tla": "AAA", "crest": None},
        "awayTeam": {"name": "B", "shortName": "B", "tla": "BBB", "crest": None},
        "score": {"fullTime": {"home": home, "away": away}},
    }


def test_build_matches_window_splits_by_local_day():
    raws = [
        _raw_match(1, "2026-06-10T15:00:00Z"),   # yesterday
        _raw_match(2, "2026-06-11T19:00:00Z", status="IN_PLAY"),  # today
        _raw_match(3, "2026-06-12T15:00:00Z", status="TIMED"),    # tomorrow
        _raw_match(4, "2026-06-09T15:00:00Z"),   # out of window -> dropped
    ]
    feed = wcf.build_matches_window(raws, "Europe/Berlin", date(2026, 6, 11), 60)
    assert [m.id for m in feed.yesterday] == [1]
    assert [m.id for m in feed.today] == [2]
    assert [m.id for m in feed.tomorrow] == [3]


def test_build_knockout_filters_and_orders_stages():
    raws = [
        _raw_match(1, "2026-07-05T19:00:00Z", stage="FINAL"),
        _raw_match(2, "2026-07-01T19:00:00Z", stage="LAST_16"),
        _raw_match(3, "2026-06-20T19:00:00Z", stage="GROUP_STAGE"),  # dropped
    ]
    feed = wcf.build_knockout(raws, 60)
    assert [s.stage for s in feed.stages] == ["LAST_16", "FINAL"]
    assert [m.id for m in feed.stages[0].matches] == [2]


def test_build_scorers_ranks_and_maps():
    raw = [
        {"player": {"name": "Kylian Mbappé"},
         "team": {"name": "France", "shortName": "France", "tla": "FRA",
                  "crest": "https://crests.football-data.org/fra.png"},
         "goals": 6},
        {"player": {"name": "Harry Kane"},
         "team": {"name": "England", "shortName": "England", "tla": "ENG", "crest": None},
         "goals": 4},
    ]
    feed = wcf.build_scorers(raw, 60)
    assert [s.rank for s in feed.scorers] == [1, 2]
    assert feed.scorers[0].player_name == "Kylian Mbappé"
    assert feed.scorers[0].team.name == "France"
    assert feed.scorers[0].goals == 6


@pytest.mark.asyncio
async def test_get_scorers_caches_within_ttl(monkeypatch):
    calls = []

    async def fake(api_key):
        calls.append(1)
        return [{"player": {"name": "X"}, "team": {"name": "Y"}, "goals": 1}]

    monkeypatch.setattr(wcf, "_fetch_scorers", fake)
    monkeypatch.setattr(wcf, "_utcnow", lambda: datetime(2026, 6, 11, 12, tzinfo=timezone.utc))
    await wcf.get_scorers("k", 60)
    await wcf.get_scorers("k", 60)
    assert len(calls) == 1
