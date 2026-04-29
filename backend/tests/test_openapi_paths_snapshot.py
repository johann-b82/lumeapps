import json
import os
from pathlib import Path

from app.main import app

CONTRACT_PATH = Path(__file__).parent / "contracts" / "openapi_paths.json"

# v1.23 C-1+: paths that have been migrated to Directus and MUST NOT
# reappear in the FastAPI OpenAPI surface. A regression that re-registers
# any of these paths fails the test before drift hits production.
DISALLOWED_PATHS: set[str] = {
    "/api/uploads",  # C-1: GET migrated to Directus upload_batches collection
}

# v1.23 C-2+: (path, method) pairs migrated to Directus where the same path
# still has surviving handlers for other methods. Use this when a partial
# migration leaves the path in the OpenAPI set but a specific method must
# not reappear.
DISALLOWED_METHODS: set[tuple[str, str]] = {
    # C-2: GET migrated to Directus signage_media collection.
    # POST on /api/signage/media remains on FastAPI.
    ("/api/signage/media", "get"),
}


def test_openapi_paths_match_snapshot():
    """CLEAN-02 / D-07: lock the FastAPI surface.

    Asserts the sorted set of OpenAPI paths matches the committed baseline.
    Catches accidental re-registration of a deleted router (e.g. me_router,
    data_router) and accidental new-route additions that bypass the planning
    workflow.

    Regenerate with:
        UPDATE_SNAPSHOTS=1 pytest backend/tests/test_openapi_paths_snapshot.py
    """
    actual = sorted(app.openapi()["paths"].keys())
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONTRACT_PATH.write_text(json.dumps(actual, indent=2) + "\n")
        return
    expected = json.loads(CONTRACT_PATH.read_text())
    assert actual == expected, (
        f"OpenAPI paths drift detected.\n"
        f"  added:   {sorted(set(actual) - set(expected))}\n"
        f"  removed: {sorted(set(expected) - set(actual))}\n"
        f"  Regenerate with UPDATE_SNAPSHOTS=1 if intentional."
    )


def test_directus_migrated_paths_are_not_reregistered():
    """v1.23 C-1+: paths migrated to Directus must not reappear in FastAPI."""
    actual = set(app.openapi()["paths"].keys())
    overlap = DISALLOWED_PATHS & actual
    assert not overlap, (
        f"the following paths were migrated to Directus but reappeared "
        f"in FastAPI OpenAPI: {sorted(overlap)}"
    )


def test_directus_migrated_methods_are_not_reregistered():
    """v1.23 C-2+: specific methods migrated to Directus must not reappear.

    Used when a partial migration leaves the path in OpenAPI (other methods
    still served by FastAPI) but a specific verb has been moved.
    """
    paths = app.openapi()["paths"]
    overlap = {
        (path, method)
        for (path, method) in DISALLOWED_METHODS
        if method in paths.get(path, {})
    }
    assert not overlap, (
        f"the following (path, method) pairs were migrated to Directus but "
        f"reappeared in FastAPI OpenAPI: {sorted(overlap)}"
    )
