from tests._atr_fixtures import build_atr_workbook_bytes
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


async def test_template_get_patch_structure(client):
    r = await client.get("/api/atr/template", headers=_auth())
    assert r.status_code == 200
    assert r.json()["id"] == 1
    assert r.json()["has_structure"] is False

    r = await client.patch("/api/atr/template", headers=_auth(),
                           json={"customer_spec": "C9312", "qa_signer_default": "Cordula Kesseler i.A."})
    assert r.status_code == 200
    assert r.json()["customer_spec"] == "C9312"

    files = {"file": ("t.xlsx", build_atr_workbook_bytes(),
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = await client.post("/api/atr/template/structure", headers=_auth(), files=files)
    assert r.status_code == 200
    assert r.json()["has_structure"] is True
    assert r.json()["structure_filename"] == "t.xlsx"
