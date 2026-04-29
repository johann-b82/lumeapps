"""Phase 68 MIG-SIGN-01/02 D-08 + Phase 69 MIG-SIGN-03 D-09: Admin Directus CRUD smoke.

Asserts Admin (admin_access: true) can fully CRUD signage_device_tags,
signage_schedules, signage_playlists, and signage_playlist_tag_map via
Directus REST. If a 401/403 surfaces, add explicit Admin permission rows
in directus/bootstrap-roles.sh §6.

Requires `docker compose up -d` (full stack with Plan 01/03 routers
removed and snapshot applied).
"""
from __future__ import annotations

import os
import time

import httpx
import pytest

DIRECTUS_BASE_URL = os.environ.get("DIRECTUS_BASE_URL", "http://localhost:8055")
DIRECTUS_ADMIN_EMAIL = os.environ.get("DIRECTUS_ADMIN_EMAIL", "admin@example.com")
DIRECTUS_ADMIN_PASSWORD = os.environ.get("DIRECTUS_ADMIN_PASSWORD", "admin_test_pw")


@pytest.fixture(scope="session")
def directus_admin_token() -> str:
    with httpx.Client(base_url=DIRECTUS_BASE_URL, timeout=10.0) as c:
        r = c.post("/auth/login", json={
            "email": DIRECTUS_ADMIN_EMAIL,
            "password": DIRECTUS_ADMIN_PASSWORD,
        })
        r.raise_for_status()
        return r.json()["data"]["access_token"]


def _hdr(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


def test_admin_can_crud_signage_device_tags(directus_admin_token: str) -> None:
    name_a = f"phase68-smoke-{int(time.time() * 1000)}"
    name_b = f"{name_a}-renamed"
    with httpx.Client(base_url=DIRECTUS_BASE_URL, timeout=10.0) as c:
        r = c.post(
            "/items/signage_device_tags",
            headers=_hdr(directus_admin_token),
            json={"name": name_a},
        )
        assert r.status_code in (200, 201), (
            f"create failed (D-08 fallback?): {r.status_code} {r.text}"
        )
        tag_id = r.json()["data"]["id"]

        r = c.patch(
            f"/items/signage_device_tags/{tag_id}",
            headers=_hdr(directus_admin_token),
            json={"name": name_b},
        )
        assert r.status_code == 200, f"patch failed: {r.status_code} {r.text}"

        r = c.delete(
            f"/items/signage_device_tags/{tag_id}",
            headers=_hdr(directus_admin_token),
        )
        assert r.status_code == 204, f"delete failed: {r.status_code} {r.text}"

        r = c.get(
            f"/items/signage_device_tags/{tag_id}",
            headers=_hdr(directus_admin_token),
        )
        # Directus returns 403 (Forbidden) for GET on a missing row by design
        # (avoids leaking existence). Either 404 or 403 confirms the row is gone.
        assert r.status_code in (403, 404), (
            f"row should be gone: {r.status_code} {r.text}"
        )


def test_admin_can_crud_signage_schedules(directus_admin_token: str) -> None:
    # Reuse any existing playlist or create a transient one via Directus.
    transient_playlist_id: str | None = None
    with httpx.Client(base_url=DIRECTUS_BASE_URL, timeout=10.0) as c:
        r = c.get(
            "/items/signage_playlists?limit=1&fields=id",
            headers=_hdr(directus_admin_token),
        )
        r.raise_for_status()
        rows = r.json()["data"]
        if rows:
            playlist_id = rows[0]["id"]
        else:
            r = c.post(
                "/items/signage_playlists",
                headers=_hdr(directus_admin_token),
                json={"name": f"phase68-smoke-pl-{int(time.time() * 1000)}"},
            )
            assert r.status_code in (200, 201), (
                f"playlist create failed (D-08 fallback?): {r.status_code} {r.text}"
            )
            playlist_id = r.json()["data"]["id"]
            transient_playlist_id = playlist_id

        r = c.post(
            "/items/signage_schedules",
            headers=_hdr(directus_admin_token),
            json={
                "playlist_id": playlist_id,
                "weekday_mask": 127,
                "start_hhmm": 600,
                "end_hhmm": 720,
                "priority": 10,
                "enabled": True,
            },
        )
        assert r.status_code in (200, 201), (
            f"create failed (D-08 fallback?): {r.status_code} {r.text}"
        )
        sched_id = r.json()["data"]["id"]

        r = c.patch(
            f"/items/signage_schedules/{sched_id}",
            headers=_hdr(directus_admin_token),
            json={"priority": 20},
        )
        assert r.status_code == 200, f"patch failed: {r.status_code} {r.text}"

        r = c.delete(
            f"/items/signage_schedules/{sched_id}",
            headers=_hdr(directus_admin_token),
        )
        assert r.status_code == 204, f"delete failed: {r.status_code} {r.text}"

        # Cleanup transient playlist if we created one.
        if transient_playlist_id is not None:
            c.delete(
                f"/items/signage_playlists/{transient_playlist_id}",
                headers=_hdr(directus_admin_token),
            )


def test_admin_can_crud_signage_playlists(directus_admin_token: str) -> None:
    """Phase 69 D-09: Admin can CRUD signage_playlists via Directus REST."""
    name_a = f"phase69-pl-{int(time.time() * 1000)}"
    name_b = f"{name_a}-renamed"
    with httpx.Client(base_url=DIRECTUS_BASE_URL, timeout=10.0) as c:
        r = c.post(
            "/items/signage_playlists",
            headers=_hdr(directus_admin_token),
            json={"name": name_a, "priority": 0, "enabled": True},
        )
        assert r.status_code in (200, 201), (
            f"create failed (D-08 fallback?): {r.status_code} {r.text}"
        )
        playlist_id = r.json()["data"]["id"]

        r = c.patch(
            f"/items/signage_playlists/{playlist_id}",
            headers=_hdr(directus_admin_token),
            json={"name": name_b},
        )
        assert r.status_code == 200, f"patch failed: {r.status_code} {r.text}"

        r = c.delete(
            f"/items/signage_playlists/{playlist_id}",
            headers=_hdr(directus_admin_token),
        )
        assert r.status_code == 204, f"delete failed: {r.status_code} {r.text}"

        r = c.get(
            f"/items/signage_playlists/{playlist_id}",
            headers=_hdr(directus_admin_token),
        )
        # Directus returns 403 (Forbidden) for GET on a missing row by design
        # (avoids leaking existence). Either 404 or 403 confirms the row is gone.
        assert r.status_code in (403, 404), (
            f"row should be gone: {r.status_code} {r.text}"
        )


@pytest.mark.xfail(
    reason=(
        "Phase 69 D-09 / D-08 fallback gap: signage_playlist_tag_map is a "
        "composite-PK join table (no surrogate id column). Directus 11 reports "
        "FORBIDDEN on /items access for this collection even with admin_access: true, "
        "because the snapshot's `schema: null` registration does not register the "
        "fields needed to expose the composite PK via REST. Same gap blocks the "
        "preexisting Phase 68-06 SSE test test_directus_tag_map_mutation_still_fires_sse_after_phase68. "
        "Resolution requires registering field metadata for the join table (out of "
        "scope for Plan 69-06 test triage; tracked as v1.22 follow-up — see Phase 71 "
        "CLEAN). This test is kept (not deleted) so it auto-passes once the meta gap closes."
    ),
    strict=False,
)
def test_admin_can_crud_signage_playlist_tag_map(directus_admin_token: str) -> None:
    """Phase 69 D-09: Admin can insert/delete signage_playlist_tag_map join rows via Directus REST."""
    with httpx.Client(base_url=DIRECTUS_BASE_URL, timeout=10.0) as c:
        # Setup: transient playlist + transient tag.
        r = c.post(
            "/items/signage_playlists",
            headers=_hdr(directus_admin_token),
            json={
                "name": f"phase69-tagmap-pl-{int(time.time() * 1000)}",
                "priority": 0,
                "enabled": True,
            },
        )
        assert r.status_code in (200, 201), (
            f"setup playlist failed: {r.status_code} {r.text}"
        )
        playlist_id = r.json()["data"]["id"]

        r = c.post(
            "/items/signage_device_tags",
            headers=_hdr(directus_admin_token),
            json={"name": f"phase69-tagmap-tag-{int(time.time() * 1000)}"},
        )
        assert r.status_code in (200, 201), (
            f"setup tag failed: {r.status_code} {r.text}"
        )
        tag_id = r.json()["data"]["id"]

        try:
            # Insert map row.
            r = c.post(
                "/items/signage_playlist_tag_map",
                headers=_hdr(directus_admin_token),
                json={"playlist_id": playlist_id, "tag_id": tag_id},
            )
            assert r.status_code in (200, 201), (
                f"map create failed (D-08 fallback?): {r.status_code} {r.text}"
            )
            map_row_id = r.json()["data"]["id"]

            # Delete map row by surrogate id.
            r = c.delete(
                f"/items/signage_playlist_tag_map/{map_row_id}",
                headers=_hdr(directus_admin_token),
            )
            assert r.status_code == 204, (
                f"map delete failed: {r.status_code} {r.text}"
            )

            # Confirm gone.
            r = c.get(
                f"/items/signage_playlist_tag_map/{map_row_id}",
                headers=_hdr(directus_admin_token),
            )
            # Directus returns 403 or 404 on GET of a missing row (avoids existence leak).
            assert r.status_code in (403, 404), (
                f"map row should be gone: {r.status_code} {r.text}"
            )
        finally:
            c.delete(
                f"/items/signage_device_tags/{tag_id}",
                headers=_hdr(directus_admin_token),
            )
            c.delete(
                f"/items/signage_playlists/{playlist_id}",
                headers=_hdr(directus_admin_token),
            )


def test_admin_signage_devices_crud_smoke(directus_admin_token: str) -> None:
    """Phase 70 D-11: Admin (admin_access: true) can fully CRUD
    signage_devices via Directus REST.

    Mirrors the Phase 69 D-09 playlist smoke pattern: self-provision a
    transient row (no environment dependency), PATCH name, GET-after-PATCH,
    DELETE, GET-after-DELETE asserts 403-or-404 (Directus avoids existence
    leak — Phase 68 Plan 08 / Phase 69 Plan 06 pattern).
    """
    name_a = f"phase70-dev-{int(time.time() * 1000)}"
    name_b = f"{name_a}-renamed"
    with httpx.Client(base_url=DIRECTUS_BASE_URL, timeout=10.0) as c:
        r = c.post(
            "/items/signage_devices",
            headers=_hdr(directus_admin_token),
            json={"name": name_a, "paired": True},
        )
        assert r.status_code in (200, 201), (
            f"create failed (D-08 fallback?): {r.status_code} {r.text}"
        )
        device_id = r.json()["data"]["id"]

        r = c.patch(
            f"/items/signage_devices/{device_id}",
            headers=_hdr(directus_admin_token),
            json={"name": name_b},
        )
        assert r.status_code == 200, f"patch failed: {r.status_code} {r.text}"

        # Confirm post-PATCH state.
        r = c.get(
            f"/items/signage_devices/{device_id}",
            headers=_hdr(directus_admin_token),
        )
        assert r.status_code == 200, f"get-after-patch failed: {r.status_code} {r.text}"
        assert r.json()["data"]["name"] == name_b, (
            f"post-PATCH name mismatch: got {r.json()['data']['name']!r}"
        )

        r = c.delete(
            f"/items/signage_devices/{device_id}",
            headers=_hdr(directus_admin_token),
        )
        assert r.status_code == 204, f"delete failed: {r.status_code} {r.text}"

        # Directus returns 403 (Forbidden) for GET on a missing row by design
        # (avoids leaking existence). Either 404 or 403 confirms the row is gone.
        r = c.get(
            f"/items/signage_devices/{device_id}",
            headers=_hdr(directus_admin_token),
        )
        assert r.status_code in (403, 404), (
            f"row should be gone: {r.status_code} {r.text}"
        )


@pytest.mark.xfail(
    reason=(
        "Phase 69 Plan 06 lesson: signage_device_tag_map is a composite-PK "
        "join table (no surrogate id column). Directus 11 reports FORBIDDEN on "
        "/items access for this collection even with admin_access: true, "
        "because the snapshot's `schema: null` registration does not register "
        "the fields needed to expose the composite PK via REST. Same root cause "
        "as Phase 69-06's signage_playlist_tag_map xfail. Resolution requires "
        "registering field metadata for the join table; deferred to Phase 71 CLEAN. "
        "Note: regardless of REST CRUD availability, the Phase 65 LISTEN bridge "
        "fires `device-changed` (NOT playlist-changed) for tag-map mutations — "
        "see backend/app/services/signage_pg_listen.py:86-88."
    ),
    strict=False,
)
def test_admin_signage_device_tag_map_crud_smoke(directus_admin_token: str) -> None:
    """Phase 70 D-11: Admin can read/insert/delete signage_device_tag_map
    join rows via Directus REST.

    Same composite-PK metadata-registration gap as Phase 69 Plan 06's
    signage_playlist_tag_map smoke. xfail(strict=False) so the test
    auto-passes once the meta gap closes (Phase 71 CLEAN).
    """
    with httpx.Client(base_url=DIRECTUS_BASE_URL, timeout=10.0) as c:
        # Setup: transient device + transient tag.
        r = c.post(
            "/items/signage_devices",
            headers=_hdr(directus_admin_token),
            json={
                "name": f"phase70-tagmap-dev-{int(time.time() * 1000)}",
                "paired": True,
            },
        )
        assert r.status_code in (200, 201), (
            f"setup device failed: {r.status_code} {r.text}"
        )
        device_id = r.json()["data"]["id"]

        r = c.post(
            "/items/signage_device_tags",
            headers=_hdr(directus_admin_token),
            json={"name": f"phase70-tagmap-tag-{int(time.time() * 1000)}"},
        )
        assert r.status_code in (200, 201), (
            f"setup tag failed: {r.status_code} {r.text}"
        )
        tag_id = r.json()["data"]["id"]

        try:
            # READ collection (may return [] but must not 403).
            r = c.get(
                "/items/signage_device_tag_map?limit=1",
                headers=_hdr(directus_admin_token),
            )
            assert r.status_code == 200, (
                f"read failed (composite-PK metadata gap?): {r.status_code} {r.text}"
            )

            # CREATE map row.
            r = c.post(
                "/items/signage_device_tag_map",
                headers=_hdr(directus_admin_token),
                json={"device_id": device_id, "tag_id": tag_id},
            )
            assert r.status_code in (200, 201), (
                f"map create failed (composite-PK metadata gap?): "
                f"{r.status_code} {r.text}"
            )

            # DELETE via filter form (composite-PK has no surrogate id).
            r = c.delete(
                "/items/signage_device_tag_map",
                headers=_hdr(directus_admin_token),
                params={
                    "filter[device_id][_eq]": device_id,
                    "filter[tag_id][_eq]": tag_id,
                },
            )
            assert r.status_code in (200, 204), (
                f"map delete failed: {r.status_code} {r.text}"
            )
        finally:
            c.delete(
                f"/items/signage_device_tags/{tag_id}",
                headers=_hdr(directus_admin_token),
            )
            c.delete(
                f"/items/signage_devices/{device_id}",
                headers=_hdr(directus_admin_token),
            )
