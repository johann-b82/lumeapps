"""Unit tests for the WM-Tippspiel scoring + ranking (no DB)."""
from __future__ import annotations

from datetime import date

from app.services.tippspiel_scoring import compute_ranking, score_tip


def test_win_result_scoring():
    assert score_tip(2, 1, 2, 1) == 5          # exact
    assert score_tip(3, 2, 2, 1) == 3          # same winner + same goal diff
    assert score_tip(3, 0, 2, 1) == 2          # same winner, different goal diff
    assert score_tip(0, 1, 2, 1) == 0          # wrong winner


def test_draw_result_scoring():
    assert score_tip(1, 1, 1, 1) == 5          # exact draw
    assert score_tip(2, 2, 1, 1) == 3          # draw tipped, not exact
    assert score_tip(1, 0, 1, 1) == 0          # not a draw tip


def test_win_tip_but_draw_result_is_zero():
    assert score_tip(2, 1, 0, 0) == 0


def test_compute_ranking_orders_by_total_and_reports_last_matchday():
    depts = ["A", "B"]
    tips = [
        {"home": "Mexico", "away": "South Africa", "department": "A", "tip_home": 2, "tip_away": 0},
        {"home": "Mexico", "away": "South Africa", "department": "B", "tip_home": 1, "tip_away": 0},
        {"home": "Spain", "away": "Brazil", "department": "A", "tip_home": 1, "tip_away": 1},
        {"home": "Spain", "away": "Brazil", "department": "B", "tip_home": 0, "tip_away": 0},
    ]
    finished = [
        {"home": "Mexico", "away": "South Africa", "score_home": 2, "score_away": 0, "date": date(2026, 6, 11)},
        {"home": "Spain", "away": "Brazil", "score_home": 1, "score_away": 1, "date": date(2026, 6, 12)},
    ]
    r = compute_ranking(tips, finished, depts)
    # A: exact(5) + exact-draw(5) = 10 ; last matchday 12.06 = 5
    # B: same-winner-diff-GD(2) + draw-tipped(3) = 5 ; last = 3
    assert r[0] == {"rank": 1, "department": "A", "last_points": 5, "total_points": 10}
    assert r[1] == {"rank": 2, "department": "B", "last_points": 3, "total_points": 5}


def test_reversed_orientation_is_aligned_to_feed():
    tips = [{"home": "South Africa", "away": "Mexico", "department": "A", "tip_home": 0, "tip_away": 2}]
    finished = [{"home": "Mexico", "away": "South Africa", "score_home": 2, "score_away": 0, "date": date(2026, 6, 11)}]
    r = compute_ranking(tips, finished, ["A"])
    assert r[0]["total_points"] == 5  # SA 0 : Mexico 2  ==  Mexico 2 : SA 0


def test_unplayed_matches_do_not_count():
    tips = [{"home": "Mexico", "away": "South Africa", "department": "A", "tip_home": 2, "tip_away": 0}]
    r = compute_ranking(tips, finished=[], departments=["A"])
    assert r[0]["total_points"] == 0
    assert r[0]["last_points"] == 0
