"""Quality KPI endpoints (v1.49) — upload + audit-findings.

Integration tests for POST /api/upload-quality and
GET /api/quality/audit-findings(/history). Each test wipes the
``quality_records`` table first so assertions stand on fixture rows only.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models import QualityRecord, UploadBatch

pytestmark = pytest.mark.asyncio


_HEADER = (
    "Nr.\tDatum\tAussteller\tAdress Nr.\tAdressen\tArtikel\tBezeichnung\t"
    "Status\tgelöscht\tArt\tProblembeschreibung\tUrsache\r\n"
)


def _build(rows: list[str]) -> bytes:
    return (_HEADER + "".join(rows)).encode("cp1252")


async def _wipe() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(QualityRecord))
        await s.execute(delete(UploadBatch).where(UploadBatch.kind == "quality"))
        await s.commit()


async def _seed(admin_client, rows: list[str]) -> None:
    await _wipe()
    body = _build(rows)
    r = await admin_client.post(
        "/api/upload-quality",
        files={"file": ("8D.txt", body, "text/plain")},
    )
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Upload endpoint
# ---------------------------------------------------------------------------


async def test_upload_quality_inserts_rows(admin_client):
    await _wipe()
    body = _build([
        "1116\t01.04.2026\tBROSE\t12040\tZIM\tAudit Major Level 1\t\t\tN\tKU AUD\t\t\r\n",
        "1127\t01.04.2026\tBROSE\t12040\tZIM\tAudit Minor Level 2\t\t\tN\tKU AUD\t\t\r\n",
    ])
    r = await admin_client.post(
        "/api/upload-quality",
        files={"file": ("8D.txt", body, "text/plain")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["rows_inserted"] == 2


async def test_upload_quality_reupload_distinguishes_insert_vs_update(admin_client):
    await _wipe()
    body = _build([
        "5050\t01.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tIN AUD\t\t\r\n",
    ])
    r1 = await admin_client.post(
        "/api/upload-quality",
        files={"file": ("8D.txt", body, "text/plain")},
    )
    assert r1.json()["rows_inserted"] == 1
    assert r1.json()["rows_updated"] == 0

    # Re-upload identical file → no inserts, one update (upsert touched it).
    r2 = await admin_client.post(
        "/api/upload-quality",
        files={"file": ("8D.txt", body, "text/plain")},
    )
    assert r2.status_code == 200
    assert r2.json()["rows_inserted"] == 0
    assert r2.json()["rows_updated"] == 1


async def test_upload_quality_reupload_overwrites_changed_fields(admin_client):
    """If the ERP user edits a 8D report's status / level and re-exports,
    re-uploading the file must reflect the new values — not the cached ones.
    """
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models import QualityRecord

    await _wipe()

    original = _build([
        "9001\t01.04.2026\tBROSE\t\t\tAudit Major Level 1\tOriginal designation\t"
        "CAR MA 4\tN\tKU AUD\t\t\r\n",
    ])
    await admin_client.post(
        "/api/upload-quality",
        files={"file": ("8D.txt", original, "text/plain")},
    )

    async with AsyncSessionLocal() as db:
        rec = (
            await db.execute(
                select(QualityRecord).where(QualityRecord.report_nr == "9001")
            )
        ).scalar_one()
        assert rec.level == 1
        assert rec.status_code == "CAR MA 4"
        assert rec.designation == "Original designation"

    # Now: same Nr., changed Artikel (Major → Minor), status, designation.
    edited = _build([
        "9001\t01.04.2026\tBROSE\t\t\tAudit Minor Level 2\tEdited designation\t"
        "CAR MI 11\tN\tKU AUD\t\t\r\n",
    ])
    r = await admin_client.post(
        "/api/upload-quality",
        files={"file": ("8D.txt", edited, "text/plain")},
    )
    payload = r.json()
    assert payload["rows_inserted"] == 0
    assert payload["rows_updated"] == 1

    async with AsyncSessionLocal() as db:
        rec = (
            await db.execute(
                select(QualityRecord).where(QualityRecord.report_nr == "9001")
            )
        ).scalar_one()
        assert rec.level == 2  # changed
        assert rec.status_code == "CAR MI 11"  # changed
        assert rec.designation == "Edited designation"  # changed


async def test_upload_quality_rejects_non_txt(admin_client):
    r = await admin_client.post(
        "/api/upload-quality",
        files={"file": ("8D.csv", b"x", "text/csv")},
    )
    assert r.status_code == 422


async def test_upload_quality_admin_only(viewer_client):
    r = await viewer_client.post(
        "/api/upload-quality",
        files={"file": ("8D.txt", _build([]), "text/plain")},
    )
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Audit-findings count endpoint
# ---------------------------------------------------------------------------


async def test_audit_findings_counts_level_1_and_2(admin_client):
    await _seed(admin_client, [
        "100\t05.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tKU AUD\t\t\r\n",
        "101\t06.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tIN AUD\t\t\r\n",
        "102\t06.04.2026\t\t\t\tAudit Minor Level 2\t\t\tN\tBH AUD\t\t\r\n",
        "103\t07.04.2026\t\t\t\tAudit Minor Level 2\t\t\tN\tEX AUD\t\t\r\n",
    ])
    r = await admin_client.get(
        "/api/quality/audit-findings?date_from=2026-04-01&date_to=2026-04-30",
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["level_1"] == 2
    assert data["level_2"] == 2


async def test_audit_findings_filter_by_audit_types(admin_client):
    await _seed(admin_client, [
        "200\t05.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tKU AUD\t\t\r\n",
        "201\t06.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tIN AUD\t\t\r\n",
        "202\t07.04.2026\t\t\t\tAudit Minor Level 2\t\t\tN\tBH AUD\t\t\r\n",
    ])
    # Only KU AUD selected → exactly 1 Level-1 finding, 0 Level-2.
    r = await admin_client.get(
        "/api/quality/audit-findings?date_from=2026-04-01&date_to=2026-04-30"
        "&audit_types=KU%20AUD",
    )
    data = r.json()
    assert data["level_1"] == 1
    assert data["level_2"] == 0


async def test_audit_findings_excludes_non_audit_art(admin_client):
    """Reklamationen rows (art empty or non-audit) must NOT count toward audits."""
    await _seed(admin_client, [
        "300\t05.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tKU AUD\t\t\r\n",
        # Has Level-1 text but art is empty (Reklamation) — should be ignored.
        "301\t06.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\t\t\t\r\n",
        # Has art KU REK (non-audit) — should be ignored.
        "302\t07.04.2026\t\t\t\tAudit Minor Level 2\t\t\tN\tKU REK\t\t\r\n",
    ])
    r = await admin_client.get(
        "/api/quality/audit-findings?date_from=2026-04-01&date_to=2026-04-30",
    )
    data = r.json()
    assert data["level_1"] == 1
    assert data["level_2"] == 0


async def test_audit_findings_rejects_unknown_audit_type(viewer_client):
    r = await viewer_client.get(
        "/api/quality/audit-findings?date_from=2026-04-01&date_to=2026-04-30"
        "&audit_types=WAT%20AUD",
    )
    assert r.status_code == 400


async def test_audit_findings_validates_date_range(viewer_client):
    # Only one bound provided → 400 (mirrors HR /kpis behavior).
    r = await viewer_client.get(
        "/api/quality/audit-findings?date_from=2026-04-01",
    )
    assert r.status_code == 400


async def test_audit_findings_history_buckets_daily_for_short_range(admin_client):
    """A 3-day window must yield 3 daily buckets (length_days <= 31 branch)."""
    await _seed(admin_client, [
        "400\t05.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tIN AUD\t\t\r\n",
        "401\t06.04.2026\t\t\t\tAudit Minor Level 2\t\t\tN\tIN AUD\t\t\r\n",
    ])
    r = await admin_client.get(
        "/api/quality/audit-findings/history"
        "?date_from=2026-04-05&date_to=2026-04-07",
    )
    assert r.status_code == 200
    points = r.json()
    assert [p["month"] for p in points] == ["2026-04-05", "2026-04-06", "2026-04-07"]
    counts = {p["month"]: (p["level_1"], p["level_2"]) for p in points}
    assert counts["2026-04-05"] == (1, 0)
    assert counts["2026-04-06"] == (0, 1)
    assert counts["2026-04-07"] == (0, 0)


async def test_audit_findings_history_breakdown_by_art(admin_client):
    """Each bucket carries a level_<n>_<ART> field per active filter code."""
    await _seed(admin_client, [
        # 05.04 — 2 Level-1 findings from two different audit types.
        "500\t05.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tBH AUD\t\t\r\n",
        "501\t05.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tKU AUD\t\t\r\n",
        # 06.04 — 1 Level-2 from internal audit.
        "502\t06.04.2026\t\t\t\tAudit Minor Level 2\t\t\tN\tIN AUD\t\t\r\n",
    ])
    r = await admin_client.get(
        "/api/quality/audit-findings/history"
        "?date_from=2026-04-05&date_to=2026-04-06",
    )
    points = r.json()
    by_day = {p["month"]: p for p in points}

    # 05.04: one BH-Level-1, one KU-Level-1, none in other slots.
    assert by_day["2026-04-05"]["level_1_BH_AUD"] == 1
    assert by_day["2026-04-05"]["level_1_KU_AUD"] == 1
    assert by_day["2026-04-05"]["level_1_IN_AUD"] == 0
    assert by_day["2026-04-05"]["level_1_EX_AUD"] == 0
    assert by_day["2026-04-05"]["level_2_BH_AUD"] == 0
    assert by_day["2026-04-05"]["level_1"] == 2
    assert by_day["2026-04-05"]["level_2"] == 0

    # 06.04: one IN-Level-2 only.
    assert by_day["2026-04-06"]["level_2_IN_AUD"] == 1
    assert by_day["2026-04-06"]["level_1"] == 0
    assert by_day["2026-04-06"]["level_2"] == 1


async def test_audit_findings_list_returns_filtered_rows(admin_client):
    """List endpoint returns the same rows the KPI cards count."""
    await _seed(admin_client, [
        "700\t05.04.2026\tBROSE\t12040\tZIM Aircraft\tAudit Major Level 1\t"
        "Dummy Major\tCAR MA 4\tN\tKU AUD\t\t\r\n",
        "701\t06.04.2026\tBROSE\t12041\tACME GmbH\tAudit Minor Level 2\t"
        "Dummy Minor\tCAR MI 11\tN\tIN AUD\t\t\r\n",
        # Reklamation — must NOT appear in list (non-audit art).
        "702\t06.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tKU REK\t\t\r\n",
    ])
    r = await admin_client.get(
        "/api/quality/audit-findings/list"
        "?date_from=2026-04-01&date_to=2026-04-30",
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 2
    # Newest first: 06.04 before 05.04.
    assert rows[0]["report_nr"] == "701"
    assert rows[0]["level"] == 2
    assert rows[0]["art"] == "IN AUD"
    assert rows[0]["customer_name"] == "ACME GmbH"
    assert rows[1]["report_nr"] == "700"
    assert rows[1]["level"] == 1
    assert rows[1]["art"] == "KU AUD"


async def test_audit_findings_list_respects_audit_types_filter(admin_client):
    await _seed(admin_client, [
        "800\t05.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tBH AUD\t\t\r\n",
        "801\t05.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tKU AUD\t\t\r\n",
    ])
    r = await admin_client.get(
        "/api/quality/audit-findings/list"
        "?date_from=2026-04-01&date_to=2026-04-30"
        "&audit_types=KU%20AUD",
    )
    rows = r.json()
    assert [row["report_nr"] for row in rows] == ["801"]


async def test_audit_findings_history_breakdown_respects_art_filter(admin_client):
    """Unchecking an audit type removes its breakdown column entirely."""
    await _seed(admin_client, [
        "600\t05.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tBH AUD\t\t\r\n",
        "601\t05.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tKU AUD\t\t\r\n",
    ])
    # Only KU AUD selected → BH key must NOT appear, KU key must.
    r = await admin_client.get(
        "/api/quality/audit-findings/history"
        "?date_from=2026-04-05&date_to=2026-04-05"
        "&audit_types=KU%20AUD",
    )
    p = r.json()[0]
    assert "level_1_KU_AUD" in p
    assert "level_1_BH_AUD" not in p
    assert p["level_1_KU_AUD"] == 1
    assert p["level_1"] == 1
