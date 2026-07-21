# backend/tests/test_audit_router.py
# pytest.ini sets asyncio_mode = auto, so plain `async def test_*` works.
#
# Focus: the compliance-relevant invariants of the Audit-Modul (v1.84) —
# mandatory-phase skips need a reason, the trail is append-only and captures
# alt→neu, nothing closes itself, and progress is derived rather than stored.
import uuid
from datetime import date, timedelta

import pytest_asyncio
import sqlalchemy as sa

from tests._auth import ADMIN_UUID, VIEWER_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


@pytest_asyncio.fixture(autouse=True)
async def _clean_audits():
    """Reset audit-module state before each test (scratch DB only).

    Norm references are seeded by the migration and never deleted here — the
    FK from audit_norm_links is ON DELETE RESTRICT and the seed is what several
    tests assert against. Their mutable flags are restored to the seeded values
    instead, so a test that verifies a clause cannot leak into a later test
    that asserts the seed starts unverified.
    """
    from app.database import AsyncSessionLocal
    from app.models import Audit, AuditNormReference, AuditTrailEntry

    async with AsyncSessionLocal() as session:
        await session.execute(sa.delete(AuditTrailEntry))
        await session.execute(sa.delete(Audit))  # cascades phases + norm links
        await session.execute(
            sa.update(AuditNormReference).values(verified=False, active=True)
        )
        await session.commit()
    yield


async def _default_template_id(client) -> str:
    r = await client.get("/api/audit/templates", headers=_auth())
    assert r.status_code == 200, r.text
    templates = r.json()
    assert templates, "migration v1_84 should seed the standard phase template"
    return templates[0]["id"]


async def _create_audit(client, **overrides) -> dict:
    payload = {
        "audit_number": f"A-{uuid.uuid4().hex[:8]}",
        "title": "Internes Systemaudit Fertigung",
        "audit_type": "intern",
        "categories": ["system"],
        "scope_label": "Fertigung",
    }
    payload.update(overrides)
    r = await client.post("/api/audit/audits", headers=_auth(), json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ── Template instantiation & progress ───────────────────────────────────


async def test_create_audit_instantiates_template_phases(client):
    template_id = await _default_template_id(client)
    audit = await _create_audit(client, template_id=template_id)

    assert len(audit["phases"]) == 10
    assert [p["position"] for p in audit["phases"]] == list(range(1, 11))
    assert audit["phases"][0]["status"] == "offen"
    assert audit["progress"] == {
        "phases_total": 10,
        "phases_relevant": 10,
        "phases_done": 0,
        "phases_not_applicable": 0,
        "percent": 0,
        "is_overdue": False,
        "overdue_phase_titles": [],
    }


async def test_editing_template_does_not_touch_existing_audit(client):
    """Phases are copied at creation — a later template edit must not rewrite history."""
    template_id = await _default_template_id(client)
    audit = await _create_audit(client, template_id=template_id)
    original_titles = [p["title"] for p in audit["phases"]]

    r = await client.patch(
        f"/api/audit/templates/{template_id}",
        headers=_auth(),
        json={"name": "Umbenannte Vorlage"},
    )
    assert r.status_code == 200

    r = await client.get(f"/api/audit/audits/{audit['id']}", headers=_auth())
    assert [p["title"] for p in r.json()["phases"]] == original_titles


async def test_progress_excludes_not_applicable_phases(client):
    template_id = await _default_template_id(client)
    audit = await _create_audit(client, template_id=template_id)
    phases = audit["phases"]

    # Mark two done and one not-applicable (with a reason).
    for phase in phases[:2]:
        r = await client.patch(
            f"/api/audit/phases/{phase['id']}",
            headers=_auth(),
            json={"status": "erledigt"},
        )
        assert r.status_code == 200, r.text
    r = await client.patch(
        f"/api/audit/phases/{phases[2]['id']}",
        headers=_auth(),
        json={"status": "nicht_zutreffend", "skip_reason": "Kein Lieferant beteiligt"},
    )
    assert r.status_code == 200, r.text

    r = await client.get(f"/api/audit/audits/{audit['id']}", headers=_auth())
    progress = r.json()["progress"]
    assert progress["phases_total"] == 10
    assert progress["phases_not_applicable"] == 1
    assert progress["phases_relevant"] == 9
    assert progress["phases_done"] == 2
    assert progress["percent"] == 22  # 2/9


# ── Mandatory-phase skip protection ─────────────────────────────────────


async def test_mandatory_phase_cannot_be_skipped_without_reason(client):
    template_id = await _default_template_id(client)
    audit = await _create_audit(client, template_id=template_id)
    phase = audit["phases"][0]
    assert phase["mandatory"] is True

    r = await client.patch(
        f"/api/audit/phases/{phase['id']}",
        headers=_auth(),
        json={"status": "nicht_zutreffend"},
    )
    assert r.status_code == 422
    assert "skip_reason" in r.text

    # Whitespace is not a justification.
    r = await client.patch(
        f"/api/audit/phases/{phase['id']}",
        headers=_auth(),
        json={"status": "nicht_zutreffend", "skip_reason": "   "},
    )
    assert r.status_code == 422

    # The phase must be untouched after both rejections.
    r = await client.get(f"/api/audit/audits/{audit['id']}", headers=_auth())
    assert r.json()["phases"][0]["status"] == "offen"


async def test_skipping_a_mandatory_phase_writes_a_phase_skip_trail_entry(client):
    template_id = await _default_template_id(client)
    audit = await _create_audit(client, template_id=template_id)
    phase = audit["phases"][3]

    r = await client.patch(
        f"/api/audit/phases/{phase['id']}",
        headers=_auth(),
        json={"status": "nicht_zutreffend", "skip_reason": "Prozess 2026 stillgelegt"},
    )
    assert r.status_code == 200

    r = await client.get(f"/api/audit/audits/{audit['id']}/trail", headers=_auth())
    skips = [e for e in r.json() if e["action"] == "phase_skip"]
    assert len(skips) == 1
    assert skips[0]["old_value"] == "offen"
    assert skips[0]["new_value"] == "nicht_zutreffend"
    assert skips[0]["reason"] == "Prozess 2026 stillgelegt"


async def test_unskipping_clears_stale_reason_but_trail_keeps_it(client):
    template_id = await _default_template_id(client)
    audit = await _create_audit(client, template_id=template_id)
    phase = audit["phases"][0]

    await client.patch(
        f"/api/audit/phases/{phase['id']}",
        headers=_auth(),
        json={"status": "nicht_zutreffend", "skip_reason": "Zunächst irrelevant"},
    )
    r = await client.patch(
        f"/api/audit/phases/{phase['id']}",
        headers=_auth(),
        json={"status": "offen"},
    )
    assert r.status_code == 200
    assert r.json()["skip_reason"] is None

    r = await client.get(f"/api/audit/audits/{audit['id']}/trail", headers=_auth())
    assert any(e.get("old_value") == "Zunächst irrelevant" for e in r.json())


async def test_completing_a_phase_defaults_the_ist_termin(client):
    template_id = await _default_template_id(client)
    audit = await _create_audit(client, template_id=template_id)

    r = await client.patch(
        f"/api/audit/phases/{audit['phases'][0]['id']}",
        headers=_auth(),
        json={"status": "erledigt"},
    )
    assert r.status_code == 200
    assert r.json()["completed_on"] == date.today().isoformat()


# ── Derived overdue state ───────────────────────────────────────────────


async def test_overdue_is_derived_from_due_dates(client):
    template_id = await _default_template_id(client)
    audit = await _create_audit(client, template_id=template_id)
    phase = audit["phases"][0]
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    r = await client.patch(
        f"/api/audit/phases/{phase['id']}",
        headers=_auth(),
        json={"due_date": yesterday},
    )
    assert r.status_code == 200
    assert r.json()["is_overdue"] is True

    r = await client.get(f"/api/audit/audits/{audit['id']}", headers=_auth())
    progress = r.json()["progress"]
    assert progress["is_overdue"] is True
    assert progress["overdue_phase_titles"] == [phase["title"]]

    # Completing it clears the flag without any stored status changing.
    await client.patch(
        f"/api/audit/phases/{phase['id']}",
        headers=_auth(),
        json={"status": "erledigt"},
    )
    r = await client.get(f"/api/audit/audits/{audit['id']}", headers=_auth())
    assert r.json()["progress"]["is_overdue"] is False


async def test_closed_audit_is_never_reported_overdue(client):
    template_id = await _default_template_id(client)
    audit = await _create_audit(client, template_id=template_id)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    await client.patch(
        f"/api/audit/phases/{audit['phases'][0]['id']}",
        headers=_auth(),
        json={"due_date": yesterday},
    )

    r = await client.post(
        f"/api/audit/audits/{audit['id']}/status",
        headers=_auth(),
        json={"status": "abgeschlossen", "note": "Alle Maßnahmen verifiziert"},
    )
    assert r.status_code == 200
    assert r.json()["progress"]["is_overdue"] is False


# ── Status transitions: explicit, logged, never automatic ───────────────


async def test_completing_all_phases_does_not_auto_close_the_audit(client):
    """"Keine automatische Schließung ohne menschliche Freigabe"."""
    template_id = await _default_template_id(client)
    audit = await _create_audit(client, template_id=template_id)

    for phase in audit["phases"]:
        r = await client.patch(
            f"/api/audit/phases/{phase['id']}",
            headers=_auth(),
            json={"status": "erledigt"},
        )
        assert r.status_code == 200

    r = await client.get(f"/api/audit/audits/{audit['id']}", headers=_auth())
    body = r.json()
    assert body["progress"]["percent"] == 100
    assert body["status"] == "geplant"  # still exactly where a human left it


async def test_closing_an_audit_requires_a_note(client):
    audit = await _create_audit(client)

    r = await client.post(
        f"/api/audit/audits/{audit['id']}/status",
        headers=_auth(),
        json={"status": "abgeschlossen"},
    )
    assert r.status_code == 422

    r = await client.post(
        f"/api/audit/audits/{audit['id']}/status",
        headers=_auth(),
        json={"status": "abgeschlossen", "note": "Freigabe QM-Leitung 2026-07-20"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "abgeschlossen"


async def test_status_change_is_logged_with_old_and_new(client):
    audit = await _create_audit(client)
    r = await client.post(
        f"/api/audit/audits/{audit['id']}/status",
        headers=_auth(),
        json={"status": "in_durchfuehrung", "note": "Audit gestartet"},
    )
    assert r.status_code == 200

    r = await client.get(f"/api/audit/audits/{audit['id']}/trail", headers=_auth())
    changes = [e for e in r.json() if e["action"] == "status_change"]
    assert len(changes) == 1
    assert changes[0]["field"] == "status"
    assert changes[0]["old_value"] == "geplant"
    assert changes[0]["new_value"] == "in_durchfuehrung"
    assert changes[0]["reason"] == "Audit gestartet"


# ── Trail integrity ─────────────────────────────────────────────────────


async def test_trail_records_actor_uuid_and_role(client):
    audit = await _create_audit(client)
    r = await client.get(f"/api/audit/audits/{audit['id']}/trail", headers=_auth())
    entry = r.json()[0]
    from tests._auth import USER_UUID

    assert entry["actor_user_id"] == USER_UUID
    assert entry["actor_role"] == "admin"
    # The synthesized placeholder email must never reach the log.
    assert "directus.example.com" not in r.text


async def test_trail_records_one_row_per_changed_field(client):
    audit = await _create_audit(client)
    r = await client.patch(
        f"/api/audit/audits/{audit['id']}",
        headers=_auth(),
        json={"title": "Neuer Titel", "lead_auditor": "M. Schmidt", "priority": 3},
    )
    assert r.status_code == 200

    r = await client.get(f"/api/audit/audits/{audit['id']}/trail", headers=_auth())
    updates = {e["field"]: e for e in r.json() if e["action"] == "update"}
    assert set(updates) == {"title", "lead_auditor", "priority"}
    assert updates["title"]["old_value"] == "Internes Systemaudit Fertigung"
    assert updates["title"]["new_value"] == "Neuer Titel"
    assert updates["priority"]["old_value"] == "2"
    assert updates["priority"]["new_value"] == "3"


async def test_unchanged_fields_produce_no_trail_noise(client):
    audit = await _create_audit(client)
    r = await client.get(f"/api/audit/audits/{audit['id']}/trail", headers=_auth())
    before = len(r.json())

    # Re-send the identical title.
    await client.patch(
        f"/api/audit/audits/{audit['id']}",
        headers=_auth(),
        json={"title": "Internes Systemaudit Fertigung"},
    )
    r = await client.get(f"/api/audit/audits/{audit['id']}/trail", headers=_auth())
    assert len(r.json()) == before


async def test_no_delete_route_exists_for_audits_or_trail(client):
    """Revisionssicherheit: audits are cancelled, never erased."""
    audit = await _create_audit(client)
    r = await client.delete(f"/api/audit/audits/{audit['id']}", headers=_auth())
    assert r.status_code == 405

    r = await client.get(f"/api/audit/audits/{audit['id']}/trail", headers=_auth())
    entry_id = r.json()[0]["id"]
    r = await client.delete(f"/api/audit/trail/{entry_id}", headers=_auth())
    assert r.status_code in (404, 405)


# ── Normmatrix master data ──────────────────────────────────────────────


async def test_seeded_norm_references_are_unverified(client):
    r = await client.get("/api/audit/norm-references", headers=_auth())
    assert r.status_code == 200
    norms = r.json()
    assert norms, "migration v1_84 should seed the Normmatrix"
    assert all(n["verified"] is False for n in norms), (
        "seeded clauses must start unverified — they are not checked against "
        "the consolidated regulation text"
    )


async def test_norm_reference_can_be_linked_and_verified(client):
    r = await client.get("/api/audit/norm-references", headers=_auth())
    norm = r.json()[0]

    audit = await _create_audit(client, norm_reference_ids=[norm["id"]])
    assert [n["id"] for n in audit["norm_references"]] == [norm["id"]]

    r = await client.patch(
        f"/api/audit/norm-references/{norm['id']}",
        headers=_auth(),
        json={"verified": True},
    )
    assert r.status_code == 200
    assert r.json()["verified"] is True


async def test_unknown_norm_reference_is_rejected(client):
    r = await client.post(
        "/api/audit/audits",
        headers=_auth(),
        json={
            "audit_number": f"A-{uuid.uuid4().hex[:8]}",
            "title": "Test",
            "audit_type": "intern",
            "categories": ["system"],
            "norm_reference_ids": [str(uuid.uuid4())],
        },
    )
    assert r.status_code == 422
    assert "unknown norm reference" in r.text


# ── Validation & auth ───────────────────────────────────────────────────


async def test_duplicate_audit_number_is_rejected(client):
    audit = await _create_audit(client)
    r = await client.post(
        "/api/audit/audits",
        headers=_auth(),
        json={
            "audit_number": audit["audit_number"],
            "title": "Zweites Audit",
            "audit_type": "intern",
            "categories": ["system"],
        },
    )
    assert r.status_code == 409


async def test_planned_end_before_start_is_rejected_on_patch(client):
    audit = await _create_audit(
        client, planned_start="2026-09-01", planned_end="2026-09-05"
    )
    r = await client.patch(
        f"/api/audit/audits/{audit['id']}",
        headers=_auth(),
        json={"planned_end": "2026-08-01"},
    )
    assert r.status_code == 422


async def test_viewer_is_denied(client):
    """Phase 1: the whole module is admin-gated at the router level."""
    client.headers["Authorization"] = f"Bearer {mint(VIEWER_UUID)}"
    r = await client.get("/api/audit/audits")
    assert r.status_code == 403


async def test_unauthenticated_is_denied(client):
    r = await client.get("/api/audit/audits")
    assert r.status_code == 401


# ── Multiple categories per audit (v1.85) ───────────────────────────────


async def test_audit_can_carry_several_categories(client):
    """The audit programme runs Prozess- and Produktaudit in one session."""
    audit = await _create_audit(client, categories=["prozess", "produkt"])
    assert audit["categories"] == ["produkt", "prozess"]  # normalised, sorted

    r = await client.get(f"/api/audit/audits/{audit['id']}", headers=_auth())
    assert r.json()["categories"] == ["produkt", "prozess"]


async def test_duplicate_categories_are_deduped(client):
    audit = await _create_audit(client, categories=["prozess", "prozess", "system"])
    assert audit["categories"] == ["prozess", "system"]


async def test_at_least_one_category_is_required(client):
    r = await client.post(
        "/api/audit/audits",
        headers=_auth(),
        json={
            "audit_number": f"A-{uuid.uuid4().hex[:8]}",
            "title": "Ohne Kategorie",
            "audit_type": "intern",
            "categories": [],
        },
    )
    assert r.status_code == 422


async def test_category_filter_matches_any_of_an_audits_categories(client):
    combined = await _create_audit(client, categories=["prozess", "produkt"])
    system_only = await _create_audit(client, categories=["system"])

    r = await client.get("/api/audit/audits?category=produkt", headers=_auth())
    ids = [a["id"] for a in r.json()]
    assert combined["id"] in ids
    assert system_only["id"] not in ids

    # The same audit must also be found under its other category.
    r = await client.get("/api/audit/audits?category=prozess", headers=_auth())
    assert combined["id"] in [a["id"] for a in r.json()]


async def test_changing_categories_is_logged(client):
    audit = await _create_audit(client, categories=["prozess"])
    r = await client.patch(
        f"/api/audit/audits/{audit['id']}",
        headers=_auth(),
        json={"categories": ["prozess", "produkt"]},
    )
    assert r.status_code == 200
    assert r.json()["categories"] == ["produkt", "prozess"]

    r = await client.get(f"/api/audit/audits/{audit['id']}/trail", headers=_auth())
    entry = next(e for e in r.json() if e["field"] == "categories")
    assert entry["old_value"] == "prozess"
    assert entry["new_value"] == "produkt, prozess"


async def test_patching_norm_references_is_reflected_in_the_response(client):
    """Regression: a raw insert left the loaded collection stale after commit."""
    r = await client.get("/api/audit/norm-references", headers=_auth())
    norms = r.json()
    first, second = norms[0]["id"], norms[1]["id"]

    audit = await _create_audit(client, norm_reference_ids=[first])
    assert [n["id"] for n in audit["norm_references"]] == [first]

    r = await client.patch(
        f"/api/audit/audits/{audit['id']}",
        headers=_auth(),
        json={"norm_reference_ids": [first, second]},
    )
    assert r.status_code == 200
    assert sorted(n["id"] for n in r.json()["norm_references"]) == sorted([first, second])

    # And removal must land too.
    r = await client.patch(
        f"/api/audit/audits/{audit['id']}",
        headers=_auth(),
        json={"norm_reference_ids": [second]},
    )
    assert [n["id"] for n in r.json()["norm_references"]] == [second]
