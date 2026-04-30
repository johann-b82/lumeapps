"""Phase 71 CLEAN-04 / D-08: absent-from check on DB_EXCLUDE_TABLES.

The v1.22 migration moved a set of collections from FastAPI CRUD to
Directus. For Directus to serve them, they must NOT appear in the
DB_EXCLUDE_TABLES env var (which is the deny-list Directus consults
when auto-introspecting Postgres tables).

This test enforces the user-locked semantics from D-08:
    assert migrated_collections.isdisjoint(set(DB_EXCLUDE_TABLES))

A complementary superset check (never-expose tables MUST appear in
DB_EXCLUDE_TABLES) lives in scripts/ci/check_db_exclude_tables_superset.sh
and is intentionally separate.
"""
import re
from pathlib import Path

import pytest


MIGRATED_COLLECTIONS = {
    "sales_records",
    "personio_employees",
    "signage_devices",
    "signage_playlists",
    "signage_playlist_items",
    "signage_device_tags",
    "signage_playlist_tag_map",
    "signage_device_tag_map",
    "signage_schedules",
    "upload_batches",  # v1.23 C-1: GET /api/uploads migrated to Directus
    "signage_media",  # v1.23 C-2: GET /api/signage/media migrated to Directus
}

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"


def _read_db_exclude_tables() -> set[str]:
    text = COMPOSE.read_text()
    m = re.search(r"^\s+DB_EXCLUDE_TABLES:\s*(.+)$", text, re.MULTILINE)
    assert m, "DB_EXCLUDE_TABLES not found in docker-compose.yml"
    raw = m.group(1).strip().strip('"').strip("'")
    return {t.strip() for t in raw.split(",") if t.strip()}


def test_migrated_collections_absent_from_db_exclude_tables():
    if not COMPOSE.is_file():
        pytest.skip(
            f"docker-compose.yml not reachable from {__file__} (parents[2]={COMPOSE}); "
            "this test runs from the host, not inside the api container."
        )
    excluded = _read_db_exclude_tables()
    # User decision D-08 (planning context): absent-from semantics
    assert MIGRATED_COLLECTIONS.isdisjoint(excluded), (
        "DB_EXCLUDE_TABLES would HIDE migrated Directus collections from "
        "Directus introspection. The following migrated collections must be "
        f"removed from DB_EXCLUDE_TABLES: {sorted(MIGRATED_COLLECTIONS & excluded)}"
    )
