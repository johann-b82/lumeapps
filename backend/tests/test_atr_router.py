# backend/tests/test_atr_router.py
# pytest.ini sets asyncio_mode = auto, so plain `async def test_*` works.
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


async def test_create_list_patch_delete_part(client):
    # create
    r = await client.post("/api/atr/parts", headers=_auth(), json={
        "part_number": "VR11S 1010 016 000",
        "part_name": "CARPET EMERGENCY EXIT HATCH",
        "drawing_number_issue": "VR11S 1010-10/D",
        "default_weight_kg": "0.413",
        "category": "CARPET",
    })
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["part_number_norm"] == "111010016000"

    # duplicate norm → 409
    r = await client.post("/api/atr/parts", headers=_auth(), json={
        "part_number": "VR11S1010016000",
    })
    assert r.status_code == 409

    # list + search
    r = await client.get("/api/atr/parts?search=EXIT", headers=_auth())
    assert r.status_code == 200
    assert any(p["id"] == pid for p in r.json())

    # patch
    r = await client.patch(f"/api/atr/parts/{pid}", headers=_auth(),
                           json={"po_pos": "050"})
    assert r.status_code == 200
    assert r.json()["po_pos"] == "050"

    # delete
    r = await client.delete(f"/api/atr/parts/{pid}", headers=_auth())
    assert r.status_code == 204
    r = await client.get(f"/api/atr/parts/{pid}", headers=_auth())
    assert r.status_code == 404
