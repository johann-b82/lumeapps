from tests._atr_pdf import make_text_pdf
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


async def _configure_smb(client):
    from app.database import AsyncSessionLocal
    from app.models import AppSettings
    from sqlalchemy import update
    from app.security.fernet import encrypt_credential
    async with AsyncSessionLocal() as db:
        await db.execute(update(AppSettings).where(AppSettings.id==1).values(
            atr_smb_host="h", atr_smb_share="s", atr_smb_user="u",
            atr_smb_password_enc=encrypt_credential("p")))
        await db.commit()


async def test_input_files_unconfigured(client):
    r = await client.get("/api/atr/deliveries/input-files", headers=_auth())
    assert r.status_code == 200 and r.json() == {"configured": False, "files": []}


async def test_input_files_and_process_via_smb(client, monkeypatch):
    await _configure_smb(client)
    from app.services import atr_fileserver as fs
    pdf = make_text_pdf("\n".join([
        "LIEFERSCHEIN Nr. 20189798 Datum 08.06.2026", "1 6060 1 STK",
        "CARPET EMERG. EXIT HATCH", "Bauteil-Index: D", "Ihre Nr. VR11S1010016000",
        "Auftrag Nr. 1024738 / 5", "Bestelldaten 4501119979/A350/CCRC/MSN830/6-Bett"]))
    monkeypatch.setattr(fs, "list_input_pdfs", lambda cfg: ["LS.pdf"])
    monkeypatch.setattr(fs, "read_input", lambda cfg, name: pdf)

    r = await client.get("/api/atr/deliveries/input-files", headers=_auth())
    assert r.json() == {"configured": True, "files": ["LS.pdf"]}

    r = await client.post("/api/atr/deliveries/input-files/process", headers=_auth(),
                          json={"filename": "LS.pdf"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["origin"] == "scan"
    assert body["source_path"].endswith("LS.pdf")
