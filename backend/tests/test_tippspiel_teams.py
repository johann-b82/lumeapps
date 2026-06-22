"""Every team that appears in the Tipps-Excel must be mapped to a feed name."""
from __future__ import annotations

from app.services.tippspiel_teams import GERMAN_TO_FEED

# The 48 distinct German team names found in WM2026_Tipps_Abteilungen.xlsx.
EXCEL_TEAMS = [
    "Algerien", "Argentinien", "Australien", "Belgien", "Bosnien-Herzegowina",
    "Brasilien", "Curaçao", "D.R. Kongo", "Deutschland", "Ecuador",
    "Elfenbeinküste", "England", "Frankreich", "Ghana", "Haiti", "Irak",
    "Iran", "Japan", "Jordanien", "Kanada", "Kap Verde", "Katar", "Kolumbien",
    "Kroatien", "Marokko", "Mexiko", "Neuseeland", "Niederlande", "Norwegen",
    "Panama", "Paraguay", "Portugal", "Saudi-Arabien", "Schottland", "Schweden",
    "Schweiz", "Senegal", "Spanien", "Südafrika", "Südkorea", "Tschechien",
    "Tunesien", "Türkei", "USA", "Uruguay", "Usbekistan", "Ägypten",
    "Österreich",
]


def test_every_excel_team_is_mapped():
    missing = [t for t in EXCEL_TEAMS if t not in GERMAN_TO_FEED]
    assert not missing, f"unmapped German team(s): {missing}"


def test_feed_names_are_unique():
    feed = list(GERMAN_TO_FEED.values())
    assert len(feed) == len(set(feed))
