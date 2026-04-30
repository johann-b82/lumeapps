"""AUTHZ parity: directus/bootstrap-roles.sh section 5 field allowlists MUST
stay set-equal with Pydantic *Read schemas.

Why: drift risk — an engineer adds a column to SalesRecordRead without
touching bootstrap-roles.sh, or vice versa. This test fails loud before
CI runs the docker stack, catching the drift in <1s.

Scope: sales_records + personio_employees only. directus_users allowlist
is a fixed 6-field literal (id, email, first_name, last_name, role, avatar)
and is validated by test_viewer_cannot_read_directus_users_secret_fields
against the live stack.

Run without docker stack:
    cd backend && pytest tests/signage/test_permission_field_allowlists.py -v
Expected runtime: <1s (pure-python; reads only bootstrap-roles.sh).

# Phase 68 (MIG-SIGN-01/02) — tags + schedules surface migrated to Directus
# signage_device_tags + signage_schedules collections; FastAPI tags router
# removed.
# Phase 69 (MIG-SIGN-03) — playlists CRUD + items GET migrated to Directus
# signage_playlists; FastAPI retains DELETE /playlists/{id} (409 reshape)
# + bulk PUT /playlists/{id}/items.
# Phase 70 (MIG-SIGN-04) — devices CRUD migrated to Directus signage_devices
# collection. PATCH /devices/{id}/calibration STAYS in FastAPI per D-00j.
# No allowlist changes: admin uses admin_access:true bypass; Viewer has no
# signage permissions per AUTHZ-02 (sales_records + personio_employees only).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.schemas._base import SalesRecordRead, EmployeeRead

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Navigate from backend/tests/signage/ -> repo root (3 levels up)
REPO_ROOT = Path(__file__).resolve().parents[3]  # repo root
BOOTSTRAP_PATH = REPO_ROOT / "directus" / "bootstrap-roles.sh"

# ---------------------------------------------------------------------------
# Compute-derived EmployeeRead fields NOT backed by personio_employees columns.
# These come from /api/data/employees/overtime (Phase 67 complete — row-data via Directus readItems('personio_employees'); overtime compute fields hydrated by /api/data/employees/overtime), not from Directus.
# Directus Viewer allowlist must NOT contain these fields.
# ---------------------------------------------------------------------------
COMPUTE_DERIVED_EMPLOYEE_FIELDS: frozenset[str] = frozenset({
    "total_hours",
    "overtime_hours",
    "overtime_ratio",
})

# ---------------------------------------------------------------------------
# Permission row UUIDs from plan 65-02 section 5.
# These are fixed and must match bootstrap-roles.sh exactly.
# ---------------------------------------------------------------------------
SALES_PERM_UUID = "b2222222-0001-4000-a000-000000000001"
EMPLOYEE_PERM_UUID = "b2222222-0002-4000-a000-000000000002"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_fields_array(script_text: str, perm_uuid: str) -> frozenset[str]:
    """Parse `ensure_permission "<uuid>" "<coll>" "read" '[...]'` and return
    the field set.

    The shell quoting pattern is a single-quoted JSON array on the same line.
    Line continuations (`\\\\n`) are collapsed to spaces before matching.

    Raises AssertionError if the UUID is not found in the script.
    """
    # Collapse shell line continuations (backslash-newline -> space)
    flat = re.sub(r"\\\n", " ", script_text)

    # Match: ensure_permission "<uuid>" "<coll>" "read" '<json-array>'
    pattern = (
        r'ensure_permission\s+"'
        + re.escape(perm_uuid)
        + r'"\s+"[^"]+"\s+"read"\s+\'(\[[^\']*\])\''
    )
    m = re.search(pattern, flat)
    if not m:
        raise AssertionError(
            f"Could not find ensure_permission call for UUID {perm_uuid!r} "
            f"in {BOOTSTRAP_PATH}. "
            f"Check that section 5 of bootstrap-roles.sh contains this UUID."
        )
    parsed = json.loads(m.group(1))
    return frozenset(parsed)


# ---------------------------------------------------------------------------
# Session-scoped fixture: read bootstrap-roles.sh once
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def bootstrap_text() -> str:
    if not BOOTSTRAP_PATH.exists():
        pytest.skip(f"bootstrap-roles.sh not found at {BOOTSTRAP_PATH} — skipping parity check")
    text = BOOTSTRAP_PATH.read_text()
    # The v1.22 migration (Backend Consolidation — Directus-First CRUD) moved
    # per-collection allowlists out of bootstrap-roles.sh into the Directus
    # snapshot apply step. The `ensure_permission` shell function is still
    # defined here for back-compat but is no longer called. Skip cleanly so
    # this drift-detection test doesn't claim a missing section as a real
    # regression — drift is now governed by `directus/snapshot.json`.
    if 'ensure_permission "' not in text:
        pytest.skip(
            "bootstrap-roles.sh no longer contains ensure_permission calls "
            "(allowlists moved to Directus snapshot in v1.22) — "
            "drift detection lives in the snapshot diff guard now"
        )
    return text


# ---------------------------------------------------------------------------
# Test 1: sales_records allowlist == SalesRecordRead.model_fields
# ---------------------------------------------------------------------------


def test_sales_records_allowlist_matches_pydantic_SalesRecordRead(
    bootstrap_text: str,
) -> None:
    """Shell field array for sales_records (UUID b2222222-0001-...)
    must be set-equal with SalesRecordRead.model_fields.keys().

    Failure means one side was updated without updating the other — the Viewer
    may be exposed to more or fewer fields than FastAPI returns.
    """
    shell_fields = _extract_fields_array(bootstrap_text, SALES_PERM_UUID)
    pydantic_fields = frozenset(SalesRecordRead.model_fields.keys())

    extra_in_shell = shell_fields - pydantic_fields
    missing_from_shell = pydantic_fields - shell_fields

    assert not extra_in_shell and not missing_from_shell, (
        f"sales_records allowlist drift detected:\n"
        f"  extra in bootstrap-roles.sh (NOT in SalesRecordRead):   {sorted(extra_in_shell)}\n"
        f"  missing from bootstrap-roles.sh (IN SalesRecordRead):   {sorted(missing_from_shell)}\n"
        f"\n"
        f"  Fix: update directus/bootstrap-roles.sh section 5 (SALES_PERM_UUID={SALES_PERM_UUID})\n"
        f"       OR update SalesRecordRead in backend/app/schemas/_base.py\n"
        f"       to match reality. Both sides must be in sync."
    )


# ---------------------------------------------------------------------------
# Test 2: personio_employees allowlist == EmployeeRead column-backed subset
# ---------------------------------------------------------------------------


def test_personio_employees_allowlist_matches_pydantic_EmployeeRead_column_subset(
    bootstrap_text: str,
) -> None:
    """Shell field array for personio_employees (UUID b2222222-0002-...)
    must be set-equal with EmployeeRead.model_fields.keys() MINUS compute-derived fields.

    COMPUTE_DERIVED_EMPLOYEE_FIELDS = {total_hours, overtime_hours, overtime_ratio}
    are sourced from /api/data/employees/overtime (Phase 67 complete — row-data via Directus readItems('personio_employees'); overtime compute fields hydrated by /api/data/employees/overtime) and must NOT appear
    in the Directus Viewer allowlist (they have no DB column in personio_employees).

    Failure modes:
    - Extra field in shell not in EmployeeRead column subset -> allowlist is too wide
    - Missing field from shell that IS in column subset -> Viewer cannot read it via Directus
    - Compute-derived field leaked into shell -> Directus would attempt to expose a non-column
    """
    shell_fields = _extract_fields_array(bootstrap_text, EMPLOYEE_PERM_UUID)
    pydantic_column_fields = frozenset(EmployeeRead.model_fields.keys()) - COMPUTE_DERIVED_EMPLOYEE_FIELDS

    # Guard: no compute-derived field leaked into the shell allowlist
    compute_leak = shell_fields & COMPUTE_DERIVED_EMPLOYEE_FIELDS
    assert not compute_leak, (
        f"Compute-derived field(s) leaked into personio_employees Viewer allowlist:\n"
        f"  leaked: {sorted(compute_leak)}\n"
        f"  These fields ({sorted(COMPUTE_DERIVED_EMPLOYEE_FIELDS)}) are sourced from\n"
        f"  /api/data/employees/overtime (Phase 67 complete — row-data via Directus readItems('personio_employees'); overtime compute fields hydrated by /api/data/employees/overtime), not from personio_employees DB columns.\n"
        f"  Remove them from bootstrap-roles.sh section 5 (UUID={EMPLOYEE_PERM_UUID})."
    )

    extra_in_shell = shell_fields - pydantic_column_fields
    missing_from_shell = pydantic_column_fields - shell_fields

    assert not extra_in_shell and not missing_from_shell, (
        f"personio_employees allowlist drift detected:\n"
        f"  extra in bootstrap-roles.sh (NOT column-backed in EmployeeRead):   {sorted(extra_in_shell)}\n"
        f"  missing from bootstrap-roles.sh (column-backed in EmployeeRead):   {sorted(missing_from_shell)}\n"
        f"\n"
        f"  Fix: update directus/bootstrap-roles.sh section 5 (UUID={EMPLOYEE_PERM_UUID})\n"
        f"       OR update EmployeeRead in backend/app/schemas/_base.py\n"
        f"       OR update COMPUTE_DERIVED_EMPLOYEE_FIELDS in this test\n"
        f"       to reflect the actual column/compute split."
    )
