"""WM-Tippspiel scoring + department ranking (pure, no DB / no I/O).

Point rule (per match & department):
    exact result                         -> 5
    win result, right winner + goal diff -> 3
    win result, right winner only        -> 2
    draw result, draw tipped (not exact) -> 3
    wrong tendency                        -> 0
"""
from __future__ import annotations

from typing import Any


def _winner(home: int, away: int) -> int:
    """1 = home win, -1 = away win, 0 = draw."""
    return (home > away) - (home < away)


def score_tip(tip_home: int, tip_away: int, res_home: int, res_away: int) -> int:
    if tip_home == res_home and tip_away == res_away:
        return 5
    if res_home == res_away:  # real result is a draw
        return 3 if tip_home == tip_away else 0
    # real result is a win
    if _winner(tip_home, tip_away) == _winner(res_home, res_away):
        return 3 if (tip_home - tip_away) == (res_home - res_away) else 2
    return 0


def compute_ranking(
    tips: list[dict[str, Any]],
    finished: list[dict[str, Any]],
    departments: list[str],
) -> list[dict[str, Any]]:
    """Rank departments by total points over all finished matches.

    ``tips``: dicts with home/away (feed names), department, tip_home, tip_away.
    ``finished``: dicts with home/away, score_home, score_away, date.
    Returns ``[{rank, department, last_points, total_points}]`` sorted by
    total desc. ``last_points`` = points from the latest played matchday.
    """
    by_pair: dict[frozenset[str], dict[str, Any]] = {
        frozenset((m["home"], m["away"])): m for m in finished
    }

    total = {d: 0 for d in departments}
    per_date: dict[str, dict[Any, int]] = {d: {} for d in departments}
    played_dates: set[Any] = set()

    for t in tips:
        dept = t["department"]
        if dept not in total:
            continue
        m = by_pair.get(frozenset((t["home"], t["away"])))
        if m is None:
            continue  # not played yet
        # Align the tip to the feed's home/away orientation.
        if t["home"] == m["home"] and t["away"] == m["away"]:
            th, ta = t["tip_home"], t["tip_away"]
        else:
            th, ta = t["tip_away"], t["tip_home"]
        pts = score_tip(th, ta, m["score_home"], m["score_away"])
        total[dept] += pts
        d = m.get("date")
        per_date[dept][d] = per_date[dept].get(d, 0) + pts
        if d is not None:
            played_dates.add(d)

    last_date = max(played_dates) if played_dates else None
    ranked = sorted(departments, key=lambda d: (-total[d], d))
    return [
        {
            "rank": i + 1,
            "department": d,
            "last_points": per_date[d].get(last_date, 0) if last_date else 0,
            "total_points": total[d],
        }
        for i, d in enumerate(ranked)
    ]
