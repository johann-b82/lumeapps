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
