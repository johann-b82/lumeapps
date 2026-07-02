from tests._atr_fixtures import build_atr_workbook_bytes
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


def _file(name="demo.xlsx", parts=None):
    data = build_atr_workbook_bytes(parts=parts)
    return {"files": (name, data,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}


async def test_preview_then_commit_then_merge(client):
    # preview: both parts are new
    r = await client.post("/api/atr/import/preview", headers=_auth(), files=_file())
    assert r.status_code == 200, r.text
    body = r.json()[0]
    assert body["new_count"] == 2 and body["updated_count"] == 0

    # commit: creates 2
    r = await client.post("/api/atr/import/commit", headers=_auth(),
                          files=_file(), data={"update_template": "true"})
    assert r.status_code == 200, r.text
    assert r.json()[0]["created"] == 2

    # re-import the SAME part number with a different weight → updated, not new
    changed = [("6060", "VR11S 1010 016 000", "CARPET EMERGENCY EXIT HATCH",
                "N/A", "VR11S 1010-10/D", 1, "0.999")]
    r = await client.post("/api/atr/import/preview", headers=_auth(),
                          files=_file(name="v2.xlsx", parts=changed))
    pv = r.json()[0]
    assert pv["updated_count"] == 1 and pv["new_count"] == 0
    assert pv["parts"][0]["status"] == "updated"

    r = await client.post("/api/atr/import/commit", headers=_auth(),
                          files=_file(name="v2.xlsx", parts=changed))
    assert r.json()[0]["updated"] == 1

    # catalog still has one row for that norm, with the new weight + source
    r = await client.get("/api/atr/parts?search=016%20000", headers=_auth())
    rows = [p for p in r.json() if p["part_number_norm"] == "111010016000"]
    assert len(rows) == 1
    assert rows[0]["default_weight_kg"] == "0.999"
    assert rows[0]["source_filename"] == "v2.xlsx"

    # template defaults were seeded from the import
    r = await client.get("/api/atr/template", headers=_auth())
    assert r.json()["nscm_code"] == "C9312"


async def test_commit_dedupes_duplicate_norm_within_one_file(client):
    dup = [
        ("6060", "VR11S 1010 016 000", "X", "N/A", "VR11S 1010-10/D", 1, "0.40"),
        ("6060", "VR11S 1010 016 000", "X", "N/A", "VR11S 1010-10/D", 1, "0.50"),
    ]
    r = await client.post("/api/atr/import/commit", headers=_auth(),
                          files=_file(parts=dup))
    assert r.status_code == 200, r.text
    rows = (await client.get("/api/atr/parts?search=016%20000", headers=_auth())).json()
    rows = [p for p in rows if p["part_number_norm"] == "111010016000"]
    assert len(rows) == 1, rows
    assert rows[0]["default_weight_kg"] == "0.500"


async def test_preview_trailing_zero_weight_is_unchanged(client):
    base = [("6060", "VR11S 1010 016 000", "X", "N/A", "VR11S 1010-10/D", 1, "0.41")]
    await client.post("/api/atr/import/commit", headers=_auth(),
                      files=_file(parts=base))
    tz = [("6060", "VR11S 1010 016 000", "X", "N/A", "VR11S 1010-10/D", 1, "0.410")]
    r = await client.post("/api/atr/import/preview", headers=_auth(),
                          files=_file(name="tz.xlsx", parts=tz))
    pv = r.json()[0]
    assert pv["unchanged_count"] == 1 and pv["updated_count"] == 0, pv
