from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


def _pdf_like_lieferschein() -> bytes:
    # A real .pdf is needed because the upload path runs pdftotext. Build a
    # tiny one-page PDF whose text layer contains a Lieferschein position.
    # One logical line per row — the parser is line-oriented.
    text = "\n".join([
        "LIEFERSCHEIN Nr. 20189798 Datum 08.06.2026",
        "1 6060 1 STK",
        "CARPET EMERG. EXIT HATCH",
        "Bauteil-Index: D",
        "Ihre Nr. VR11S1010016000",
        "Auftrag Nr. 1024738 / 5",
        "Bestelldaten 4501119979/A350/CCRC/MSN830/6-Bett",
    ])
    from tests._atr_pdf import make_text_pdf
    return make_text_pdf(text)


async def test_upload_creates_draft_with_items(client):
    files = {"file": ("LS.pdf", _pdf_like_lieferschein(), "application/pdf")}
    r = await client.post("/api/atr/deliveries/upload", headers=_auth(), files=files)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["compartment"] == "CCRC"
    assert len(body["items"]) >= 1
    did = body["id"]

    # patch header
    r = await client.patch(f"/api/atr/deliveries/{did}", headers=_auth(),
                           json={"container_number": "AK111000"})
    assert r.json()["container_number"] == "AK111000"

    # patch an item
    iid = body["items"][0]["id"]
    r = await client.patch(f"/api/atr/deliveries/{did}/items/{iid}", headers=_auth(),
                           json={"weight_kg": "0.420"})
    assert r.json()["weight_kg"] == "0.420"

    # list + get
    assert any(d["id"] == did for d in (await client.get("/api/atr/deliveries", headers=_auth())).json())
    assert (await client.get(f"/api/atr/deliveries/{did}", headers=_auth())).status_code == 200


async def test_input_files_empty_when_unset(client):
    r = await client.get("/api/atr/deliveries/input-files", headers=_auth())
    assert r.status_code == 200
    assert r.json() == {"configured": False, "files": []}


async def test_container_label_combines_assigned_deliveries(client):
    files = {"file": ("LS.pdf", _pdf_like_lieferschein(), "application/pdf")}
    ids = []
    for _ in range(2):
        r = await client.post("/api/atr/deliveries/upload", headers=_auth(), files=files)
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    # nothing assigned yet → 404
    r = await client.get("/api/atr/deliveries/container-label", headers=_auth(),
                         params={"nr": "AK222000"})
    assert r.status_code == 404
    for did in ids:
        r = await client.patch(f"/api/atr/deliveries/{did}", headers=_auth(),
                               json={"container_number": "AK222000"})
        assert r.status_code == 200
    # list exposes the container number
    rows = (await client.get("/api/atr/deliveries", headers=_auth())).json()
    assert all(d["container_number"] == "AK222000" for d in rows if d["id"] in ids)

    r = await client.get("/api/atr/deliveries/container-label", headers=_auth(),
                         params={"nr": "AK222000"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert 'filename="Container_AK222000.docx"' in r.headers["content-disposition"]
    from io import BytesIO

    from docx import Document
    text = "\n".join(p.text for p in Document(BytesIO(r.content)).paragraphs)
    assert text.startswith("Container AK222000")
    assert text.count("BA 1024738") == 2
