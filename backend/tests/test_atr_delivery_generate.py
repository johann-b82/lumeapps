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


async def test_generate_scan_origin_writes_to_share(client, monkeypatch):
    await _set_structure(client)
    from app.services import atr_fileserver as fs
    seen = {}
    monkeypatch.setattr(fs, "write_output", lambda cfg, name, data: seen.__setitem__(name, 1))
    monkeypatch.setattr(fs, "archive_input", lambda cfg, name: seen.__setitem__("arch", name))
    # configure SMB + create a scan-origin delivery directly
    from app.database import AsyncSessionLocal
    from app.models import AppSettings, AtrDelivery, AtrDeliveryItem
    from sqlalchemy import update
    from datetime import datetime, timezone
    from app.security.fernet import encrypt_credential
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await db.execute(update(AppSettings).where(AppSettings.id==1).values(
            atr_smb_host="h", atr_smb_share="s", atr_smb_user="u",
            atr_smb_password_enc=encrypt_credential("p")))
        d = AtrDelivery(source_filename="LS.pdf", status="draft", origin="scan",
            source_path="0900 - EDV/Test_ATR/Input/LS.pdf", ba_auftrag="1024738",
            set_title="SET 6 BED CCRC", created_at=now, updated_at=now)
        d.items.append(AtrDeliveryItem(pos=1, supplier_article_code="6060",
            part_number="VR11S 1010 016 000", part_number_norm="111010016000",
            part_name="X", category="CARPET", qty=1, match_status="matched", row_order=1))
        db.add(d); await db.commit(); did = d.id
    r = await client.post(f"/api/atr/deliveries/{did}/generate", headers=_auth(), json={})
    assert r.status_code == 200, r.text
    assert any(n.endswith(".xlsx") for n in seen) and "arch" in seen
