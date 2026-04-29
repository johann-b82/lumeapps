"""Canonical default settings — source of truth for reset.

The Alembic migration that creates `app_settings` also seeds a row with
these same values, duplicated intentionally (migrations are snapshots;
they must not import live app code — see RESEARCH §Anti-Patterns).

Per D-07: resetting via PUT /api/settings with this dict also clears the
logo columns (logo_data / logo_mime / logo_updated_at set to NULL).
Per D-19: frontend never reads this module; it is backend-only.
"""
from typing import Final

DEFAULT_SETTINGS: Final[dict[str, str]] = {
    "color_primary": "oklch(0.55 0.15 250)",
    "color_accent": "oklch(0.70 0.18 150)",
    "color_background": "oklch(1.00 0 0)",
    "color_foreground": "oklch(0.15 0 0)",
    "color_muted": "oklch(0.90 0 0)",
    "color_destructive": "oklch(0.55 0.22 25)",
    "app_name": "KPI Dashboard",
}
