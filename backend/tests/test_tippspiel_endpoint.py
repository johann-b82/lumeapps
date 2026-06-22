"""WM-Tippspiel upload + ranking endpoints (v1.61).

WIPES tippspiel_tips — run only against the disposable acm_kpi_test DB.
"""
from __future__ import annotations

from io import BytesIO

import openpyxl
import pytest
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models import TippspielTip, UploadBatch

pytestmark = pytest.mark.asyncio

_HEADER = [
    "Gruppe", "Datum", "Spiel",
    "Büro-Admin / Hamburg", "Wandverkleidung", "Schaum / Montage",
    "Näherei / Teppich", "ACM-Team: Memmingen", "Ergebnis ", "Punkte ",
]


def _build(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "WM 2026 Tipps"
    ws.append(_HEADER)
    for r in rows:
        ws.append(list(r) + [None] * (len(_HEADER) - len(r)))
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _wipe() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(TippspielTip))
        await s.execute(delete(UploadBatch).where(UploadBatch.kind == "tippspiel"))
        await s.commit()


_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def test_upload_tippspiel_inserts_rows(admin_client):
    await _wipe()
    body = _build([
        ["A", "Do., 11.06.", "Mexiko – Südafrika", "2:1", "2:0", "1:1", "2:1", "0:0"],
        ["A", "Fr., 12.06.", "Südkorea – Tschechien", "2:0", "1:3", "1:2", "1:1", "0:0"],
    ])
    r = await admin_client.post(
        "/api/upload-tippspiel", files={"file": ("tips.xlsx", body, _XLSX)}
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["rows_inserted"] == 10  # 2 matches × 5 departments
    assert payload["rows_updated"] == 0
    assert len(payload["departments"]) == 5
    assert payload["errors"] == []


async def test_reupload_updates(admin_client):
    await _wipe()
    body = _build([
        ["A", "Do., 11.06.", "Mexiko – Südafrika", "2:1", "2:0", "1:1", "2:1", "0:0"],
    ])
    await admin_client.post("/api/upload-tippspiel", files={"file": ("t.xlsx", body, _XLSX)})
    body2 = _build([
        ["A", "Do., 11.06.", "Mexiko – Südafrika", "3:0", "2:0", "1:1", "2:1", "0:0"],
    ])
    r = await admin_client.post("/api/upload-tippspiel", files={"file": ("t.xlsx", body2, _XLSX)})
    assert r.json()["rows_inserted"] == 0
    assert r.json()["rows_updated"] == 5


async def test_ranking_endpoint_lists_all_departments(admin_client):
    await _wipe()
    body = _build([
        ["A", "Do., 11.06.", "Mexiko – Südafrika", "2:1", "2:0", "1:1", "2:1", "0:0"],
    ])
    await admin_client.post("/api/upload-tippspiel", files={"file": ("t.xlsx", body, _XLSX)})

    r = await admin_client.get("/api/worldcup/embed/tippspiel")
    assert r.status_code == 200, r.text
    ranking = r.json()["ranking"]
    assert len(ranking) == 5
    assert [row["rank"] for row in ranking] == [1, 2, 3, 4, 5]
    # no api key configured in the test DB -> no results -> all zero
    assert all(row["total_points"] == 0 for row in ranking)


async def test_ranking_empty_when_no_tips(admin_client):
    await _wipe()
    r = await admin_client.get("/api/worldcup/embed/tippspiel")
    assert r.status_code == 200, r.text
    assert r.json()["ranking"] == []
