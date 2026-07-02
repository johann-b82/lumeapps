# backend/tests/test_atr_deliver.py
import pytest
from tests._atr_fixtures import build_atr_workbook_bytes
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


async def _seed_template_and_delivery(client, origin):
    # set structural template
    files = {"file": ("t.xlsx", build_atr_workbook_bytes(),
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    await client.post("/api/atr/template/structure", headers=_auth(), files=files)
    from app.database import AsyncSessionLocal
    from app.models import AtrDelivery, AtrDeliveryItem
    from datetime import datetime, timezone
    from decimal import Decimal
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        d = AtrDelivery(source_filename="LS.pdf", status="draft", origin=origin,
                        source_path=("0900 - EDV/Test_ATR/Input/LS.pdf" if origin=="scan" else None),
                        ba_auftrag="1024738", set_title="SET 6 BED CCRC", po_number="4501119979",
                        msn="830", created_at=now, updated_at=now)
        d.items.append(AtrDeliveryItem(pos=1, supplier_article_code="6060",
            part_number="VR11S 1010 016 000", part_number_norm="111010016000",
            part_name="CARPET EMERGENCY EXIT HATCH", drawing_number_issue="VR11S 1010-10/D",
            category="CARPET", qty=1, weight_kg=Decimal("0.413"), po_pos="050",
            match_status="matched", row_order=1))
        db.add(d); await db.commit(); await db.refresh(d)
        return d.id


async def test_deliver_writes_and_archives_for_scan(client, monkeypatch):
    did = await _seed_template_and_delivery(client, origin="scan")
    from app.services import atr_fileserver as fs
    written = {}
    monkeypatch.setattr(fs, "write_output", lambda cfg, name, data: written.__setitem__(name, len(data)))
    monkeypatch.setattr(fs, "archive_input", lambda cfg, name: written.__setitem__("archived", name))
    # make config "available"
    from app.database import AsyncSessionLocal
    from app.models import AppSettings
    from sqlalchemy import update
    async with AsyncSessionLocal() as db:
        await db.execute(update(AppSettings).where(AppSettings.id==1).values(
            atr_smb_host="h", atr_smb_share="s", atr_smb_user="u",
            atr_smb_password_enc=__import__("app.security.fernet", fromlist=["encrypt_credential"]).encrypt_credential("p")))
        await db.commit()

    from app.services.atr_deliver import generate_and_deliver
    from app.models import AtrDelivery
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    async with AsyncSessionLocal() as db:
        d = (await db.execute(select(AtrDelivery).options(selectinload(AtrDelivery.items)).where(AtrDelivery.id==did))).scalar_one()
        row = (await db.execute(select(AppSettings).where(AppSettings.id==1))).scalar_one()
        man = await generate_and_deliver(db, d, row)
    assert any(n.endswith(".xlsx") for n in written) and "archived" in written
    assert man.delivery_id == did


async def test_deliver_upload_origin_does_not_write(client, monkeypatch):
    did = await _seed_template_and_delivery(client, origin="upload")
    from app.services import atr_fileserver as fs
    written = {}
    monkeypatch.setattr(fs, "write_output", lambda *a: written.setdefault("x", 1))
    from app.database import AsyncSessionLocal
    from app.services.atr_deliver import generate_and_deliver
    from app.models import AtrDelivery, AppSettings
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    async with AsyncSessionLocal() as db:
        d = (await db.execute(select(AtrDelivery).options(selectinload(AtrDelivery.items)).where(AtrDelivery.id==did))).scalar_one()
        row = (await db.execute(select(AppSettings).where(AppSettings.id==1))).scalar_one()
        await generate_and_deliver(db, d, row)
    assert written == {}
