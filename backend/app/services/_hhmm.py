"""HHMM packed-integer helpers and timezone-aware now extraction — D-04.

Centralizes all timezone handling for the signage schedule resolver so the
resolver core stays integer-only. Bit ordering: 0=Mon..6=Sun (D-05).

Uses ``datetime.weekday()`` (returns 0..6 Mon..Sun), NOT ``isoweekday()``
(1..7 Mon..Sun) — Pitfall 2.
"""
from __future__ import annotations

import datetime
import zoneinfo


def hhmm_to_time(i: int) -> datetime.time:
    """Convert packed HHMM integer (e.g., 730 → 07:30) to ``datetime.time``.

    Raises ``ValueError`` on invalid components (e.g., minute > 59) — catches
    in-range-but-structurally-invalid values like 1299 that the DB CHECK
    constraint does not reject (Pitfall 3).
    """
    return datetime.time(hour=i // 100, minute=i % 100)


def time_to_hhmm(t: datetime.time) -> int:
    """Convert ``datetime.time`` to packed HHMM integer (inverse of hhmm_to_time)."""
    return t.hour * 100 + t.minute


def now_hhmm_in_tz(tz_name: str) -> tuple[int, int]:
    """Return ``(weekday, hhmm)`` for *now* in the given IANA timezone.

    weekday: 0=Mon..6=Sun (matches the weekday_mask bit ordering D-05).
    hhmm:    packed integer in [0, 2359].

    Called once per resolve; tests override behaviour by passing explicit ``now``
    to the resolver instead of mocking this function (Pitfall 5).
    """
    now = datetime.datetime.now(zoneinfo.ZoneInfo(tz_name))
    return now.weekday(), time_to_hhmm(now.time())
