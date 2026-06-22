"""German team name → football-data.org name map for the WM 2026 Tippspiel.

The Tipps-Excel uses German team names; the results feed (football-data.org)
uses English names. Every distinct team that appears in the Excel is mapped
here so a tip can be matched to its real result. ``test_tippspiel_teams``
asserts the map covers every Excel name (no silent gaps).
"""
from __future__ import annotations

# German (Excel) -> football-data.org team name.
GERMAN_TO_FEED: dict[str, str] = {
    "Algerien": "Algeria",
    "Argentinien": "Argentina",
    "Australien": "Australia",
    "Belgien": "Belgium",
    "Bosnien-Herzegowina": "Bosnia-Herzegovina",
    "Brasilien": "Brazil",
    "Curaçao": "Curaçao",
    "D.R. Kongo": "Congo DR",
    "Deutschland": "Germany",
    "Ecuador": "Ecuador",
    "Elfenbeinküste": "Ivory Coast",
    "England": "England",
    "Frankreich": "France",
    "Ghana": "Ghana",
    "Haiti": "Haiti",
    "Irak": "Iraq",
    "Iran": "Iran",
    "Japan": "Japan",
    "Jordanien": "Jordan",
    "Kanada": "Canada",
    "Kap Verde": "Cape Verde Islands",
    "Katar": "Qatar",
    "Kolumbien": "Colombia",
    "Kroatien": "Croatia",
    "Marokko": "Morocco",
    "Mexiko": "Mexico",
    "Neuseeland": "New Zealand",
    "Niederlande": "Netherlands",
    "Norwegen": "Norway",
    "Panama": "Panama",
    "Paraguay": "Paraguay",
    "Portugal": "Portugal",
    "Saudi-Arabien": "Saudi Arabia",
    "Schottland": "Scotland",
    "Schweden": "Sweden",
    "Schweiz": "Switzerland",
    "Senegal": "Senegal",
    "Spanien": "Spain",
    "Südafrika": "South Africa",
    "Südkorea": "South Korea",
    "Tschechien": "Czechia",
    "Tunesien": "Tunisia",
    "Türkei": "Turkey",
    "USA": "United States",
    "Uruguay": "Uruguay",
    "Usbekistan": "Uzbekistan",
    "Ägypten": "Egypt",
    "Österreich": "Austria",
}


def to_feed_name(german: str) -> str | None:
    """Map a German team name to the feed name; None if unknown."""
    return GERMAN_TO_FEED.get(german.strip())
