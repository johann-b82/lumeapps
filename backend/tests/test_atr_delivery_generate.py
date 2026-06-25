from tests._atr_fixtures import build_atr_workbook_bytes
from tests._atr_pdf import make_text_pdf
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


async def _set_structure(client):
    files = {"file": ("t.xlsx", build_atr_workbook_bytes(),
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    await client.post("/api/atr/template/structure", headers=_auth(), files=files)


async def _draft(client):
    text = "\n".join([
        "LIEFERSCHEIN Nr. 20189798 Datum 08.06.2026",
        "1 6060 1 STK",
        "CARPET EMERG. EXIT HATCH",
        "Bauteil-Index: D",
        "Ihre Nr. VR11S1010016000",
        "Auftrag Nr. 1024738 / 5",
        "Bestelldaten 4501119979/A350/CCRC/MSN830/6-Bett",
    ])
    files = {"file": ("LS.pdf", make_text_pdf(text), "application/pdf")}
    return (await client.post("/api/atr/deliveries/upload", headers=_auth(), files=files)).json()


async def test_generate_and_download(client):
    await _set_structure(client)
    d = await _draft(client)
    did = d["id"]
    r = await client.post(f"/api/atr/deliveries/{did}/generate", headers=_auth(),
                          json={})
    assert r.status_code == 200, r.text
    man = r.json()
    assert "atr_xlsx" in man["files"] and "label_docx" in man["files"]
    # downloads
    rx = await client.get(f"/api/atr/deliveries/{did}/files/atr_xlsx", headers=_auth())
    assert rx.status_code == 200 and rx.content[:2] == b"PK"  # xlsx is a zip
    rd = await client.get(f"/api/atr/deliveries/{did}/files/label_docx", headers=_auth())
    assert rd.status_code == 200 and rd.content[:2] == b"PK"
    if man["pdf_available"]:
        rp = await client.get(f"/api/atr/deliveries/{did}/files/atr_pdf", headers=_auth())
        assert rp.status_code == 200 and rp.content[:5] == b"%PDF-"
