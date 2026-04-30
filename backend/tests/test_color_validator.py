"""Unit tests for the BRAND-09 color validator.

Pure unit tests — no DB, no HTTP client. Exercises _validate_oklch and
SettingsUpdate directly to lock down the CSS-injection blacklist.
"""
import pytest
import pytest_asyncio
from pydantic import ValidationError

from app.schemas import SettingsUpdate
from app.schemas._base import _validate_oklch


# Override the autouse `reset_settings` fixture from conftest.py for this module.
# These tests are pure unit tests (no DB, no HTTP) — the DB reset is unnecessary
# and would fail if the app_settings table doesn't yet exist in the parallel
# Wave 2 tree (04-02 creates the migration, we only need schemas).
@pytest_asyncio.fixture(autouse=True)
async def reset_settings():
    yield

VALID_PAYLOAD = {
    "color_primary": "oklch(0.55 0.15 250)",
    "color_accent": "oklch(0.70 0.18 150)",
    "color_background": "oklch(1 0 0)",
    "color_foreground": "oklch(0.15 0 0)",
    "color_muted": "oklch(0.90 0 0)",
    "color_destructive": "oklch(0.55 0.22 25)",
    "app_name": "Test App",
    "default_language": "EN",
}


# --- Happy path ---

@pytest.mark.parametrize(
    "good",
    [
        "oklch(0.55 0.15 250)",
        "oklch(0.5 0.15 250deg)",
        "oklch(55% 0.15 250)",
        "oklch(1 0 0)",
        "oklch(0.15 0.0 0)",
        "oklch(0.55 0.22 -25)",
    ],
)
def test_validate_oklch_accepts_valid_forms(good):
    assert _validate_oklch(good) == good


# --- Forbidden characters (D-10 full charset) ---

@pytest.mark.parametrize(
    "bad_char",
    [";", "{", "}", '"', "'", "`", "\\", "<", ">"],
)
def test_validate_oklch_rejects_forbidden_char(bad_char):
    with pytest.raises(ValueError, match="forbidden character"):
        _validate_oklch(f"oklch(0.5 0.15 250){bad_char}")


# --- Forbidden tokens ---

@pytest.mark.parametrize(
    "bad_token",
    ["url(", "expression(", "/*", "*/"],
)
def test_validate_oklch_rejects_forbidden_token(bad_token):
    with pytest.raises(ValueError, match="forbidden token"):
        _validate_oklch(f"oklch(0.5 0.15 250) {bad_token}")


# --- Regex fallthrough ---

@pytest.mark.parametrize(
    "junk",
    ["", "rgb(0,0,0)", "#ffffff", "oklch", "oklch()", "oklch(a b c)", "not-a-color"],
)
def test_validate_oklch_rejects_non_oklch(junk):
    with pytest.raises(ValueError):
        _validate_oklch(junk)


# --- SettingsUpdate integration ---

def test_settings_update_accepts_canonical_payload():
    SettingsUpdate(**VALID_PAYLOAD)  # no raise


def test_settings_update_rejects_semicolon_in_color():
    bad = {**VALID_PAYLOAD, "color_primary": "oklch(0.5 0.15 250); x"}
    with pytest.raises(ValidationError):
        SettingsUpdate(**bad)


def test_settings_update_rejects_url_function():
    bad = {**VALID_PAYLOAD, "color_accent": "oklch(0.5 0.15 url(evil))"}
    with pytest.raises(ValidationError):
        SettingsUpdate(**bad)


def test_settings_update_rejects_unknown_language():
    bad = {**VALID_PAYLOAD, "default_language": "FR"}
    with pytest.raises(ValidationError):
        SettingsUpdate(**bad)


@pytest.mark.parametrize("bad_name", ["", "x" * 101])
def test_settings_update_rejects_bad_app_name(bad_name):
    bad = {**VALID_PAYLOAD, "app_name": bad_name}
    with pytest.raises(ValidationError):
        SettingsUpdate(**bad)
