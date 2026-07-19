import pytest
from tests._atr_pdf import make_text_pdf
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


_LS = "\n".join(["LIEFERSCHEIN Nr. 20189798 Datum 08.06.2026", "1 6060 1 STK",
    "CARPET EMERG. EXIT HATCH", "Bauteil-Index: D", "Ihre Nr. VR11S1010016000",
    "Auftrag Nr. 1024738 / 5", "Bestelldaten 4501119979/A350/CCRC/MSN830/6-Bett"])


async def _configure(client, auto: bool):
    from app.database import AsyncSessionLocal
    from app.models import AppSettings
    from sqlalchemy import update
    from app.security.fernet import encrypt_credential
    # structural template (needed for auto generate)
    from tests._atr_fixtures import build_atr_workbook_bytes
    await client.post("/api/atr/template/structure", headers=_auth(),
        files={"file": ("t.xlsx", build_atr_workbook_bytes(),
               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    async with AsyncSessionLocal() as db:
        await db.execute(update(AppSettings).where(AppSettings.id==1).values(
            atr_smb_host="h", atr_smb_share="s", atr_smb_user="u",
            atr_smb_password_enc=encrypt_credential("p"),
            atr_scan_interval_s=60, atr_auto_mode=auto))
        await db.commit()


async def test_scan_review_creates_draft(client, monkeypatch):
    await _configure(client, auto=False)
    from app.services import atr_fileserver as fs
    monkeypatch.setattr(fs, "list_input_pdfs", lambda cfg: ["LS.pdf"])
    monkeypatch.setattr(fs, "read_input", lambda cfg, name: make_text_pdf(_LS))
    wrote = {}
    monkeypatch.setattr(fs, "write_output", lambda *a: wrote.setdefault("x", 1))
    from app.scheduler import _run_atr_scan
    await _run_atr_scan()
    r = await client.get("/api/atr/deliveries", headers=_auth())
    assert any(d["source_filename"] == "LS.pdf" for d in r.json())
    assert wrote == {}  # review mode: no output written

    # second scan must SKIP the already-linked file
    await _run_atr_scan()
    r = await client.get("/api/atr/deliveries", headers=_auth())
    assert sum(1 for d in r.json() if d["source_filename"] == "LS.pdf") == 1


async def test_scan_reprocesses_once_past_draft(client, monkeypatch):
    # A same-named file is only skipped while an OPEN draft awaits review.
    # Once the delivery moves past draft, a re-appearing file is processed again.
    await _configure(client, auto=False)
    from app.services import atr_fileserver as fs
    monkeypatch.setattr(fs, "list_input_pdfs", lambda cfg: ["LS.pdf"])
    monkeypatch.setattr(fs, "read_input", lambda cfg, name: make_text_pdf(_LS))
    monkeypatch.setattr(fs, "write_output", lambda *a: None)
    from app.scheduler import _run_atr_scan
    await _run_atr_scan()  # creates draft
    # flip the draft to 'generated' (admin acted, but file still in Input)
    from app.database import AsyncSessionLocal
    from app.models import AtrDelivery
    from sqlalchemy import update, select, func
    async with AsyncSessionLocal() as db:
        await db.execute(update(AtrDelivery)
            .where(AtrDelivery.source_filename == "LS.pdf")
            .values(status="generated"))
        await db.commit()
    await _run_atr_scan()  # same file → now a fresh draft, not silently ignored
    async with AsyncSessionLocal() as db:
        n = (await db.execute(select(func.count()).select_from(AtrDelivery)
            .where(AtrDelivery.source_filename == "LS.pdf"))).scalar_one()
    assert n == 2  # one 'generated' + one new 'draft'


async def test_scan_auto_writes_and_archives(client, monkeypatch):
    await _configure(client, auto=True)
    from app.services import atr_fileserver as fs
    monkeypatch.setattr(fs, "list_input_pdfs", lambda cfg: ["LS.pdf"])
    monkeypatch.setattr(fs, "read_input", lambda cfg, name: make_text_pdf(_LS))
    seen = {}
    monkeypatch.setattr(fs, "write_output", lambda cfg, name, data: seen.__setitem__(name, 1))
    monkeypatch.setattr(fs, "archive_input", lambda cfg, name: seen.__setitem__("arch", name))
    from app.scheduler import _run_atr_scan
    await _run_atr_scan()
    assert any(n.endswith(".xlsx") for n in seen) and "arch" in seen


def test_reschedule_atr_scan_removes_on_zero():
    from app.scheduler import reschedule_atr_scan, ATR_SCAN_JOB_ID, scheduler
    reschedule_atr_scan(0)
    assert scheduler.get_job(ATR_SCAN_JOB_ID) is None


async def test_scan_auto_failure_retries(client, monkeypatch):
    # configure SMB + auto, but DO NOT set a structural template → generate fails
    from app.database import AsyncSessionLocal
    from app.models import AppSettings, AtrDelivery
    from sqlalchemy import update, select, func
    from app.security.fernet import encrypt_credential
    async with AsyncSessionLocal() as db:
        await db.execute(update(AppSettings).where(AppSettings.id==1).values(
            atr_smb_host="h", atr_smb_share="s", atr_smb_user="u",
            atr_smb_password_enc=encrypt_credential("p"),
            atr_scan_interval_s=60, atr_auto_mode=True))
        await db.commit()
    from app.services import atr_fileserver as fs
    monkeypatch.setattr(fs, "list_input_pdfs", lambda cfg: ["LS.pdf"])
    monkeypatch.setattr(fs, "read_input", lambda cfg, name: make_text_pdf(_LS))
    from app.scheduler import _run_atr_scan
    await _run_atr_scan()  # generation fails (no template) → draft deleted
    async with AsyncSessionLocal() as db:
        n = (await db.execute(select(func.count()).select_from(AtrDelivery).where(
            AtrDelivery.source_filename=="LS.pdf"))).scalar_one()
    assert n == 0  # stuck draft was removed so the file will be retried
