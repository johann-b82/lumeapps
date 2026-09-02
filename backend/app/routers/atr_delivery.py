"""/api/atr/deliveries/* — admin-gated Lieferschein ingest + review (Phase B).

Generation endpoints (Wave 2): POST /{id}/generate, GET /{id}/files/{kind}.

Compute-justified: clause 1 (file parsing + document generation + SMB I/O) —
parses Lieferschein files, generates the ATR XLSX/PDF/DOCX artifacts, and reads
input files off an SMB share; none expressible as a Directus collection read.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import AtrDelivery, AtrDeliveryItem, AtrTemplate
from app.schemas import (
    AtrDeliveryItemRead, AtrDeliveryItemUpdate, AtrDeliveryRead,
    AtrDeliverySummary, AtrDeliveryUpdate, AtrGenerateManifest,
)
from app.security.directus_auth import get_current_user, require_atr_fair
from app.services.atr_lieferschein import parse_lieferschein
from app.services.atr_match import MatchedDelivery, match_positions

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/atr/deliveries", tags=["atr"],
    dependencies=[Depends(get_current_user), Depends(require_atr_fair)],
)


def _parse_datum(s: str | None):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d.%m.%Y").date()
    except ValueError:
        return None


async def _persist_draft(db: AsyncSession, md: MatchedDelivery) -> AtrDelivery:
    now = datetime.now(timezone.utc)
    today = now.date()
    row = AtrDelivery(
        source_filename=md.source_filename, lieferschein_nr=md.lieferschein_nr,
        datum=_parse_datum(md.datum), ba_auftrag=md.ba_auftrag, po_number=md.po_number,
        ac_programme=md.ac_programme, programme_reason=md.programme_reason,
        compartment=md.compartment, msn=md.msn,
        bed_config=md.bed_config, set_title=md.set_title,
        atr_number=None, container_number=None,
        weighing_date=today, testing_date=today, qa_signer=None,
        max_guaranteed_weight_kg=None, status="draft",
        created_at=now, updated_at=now,
    )
    # default qa_signer from the template singleton, if set
    tmpl = (await db.execute(select(AtrTemplate).where(AtrTemplate.id == 1))).scalar_one_or_none()
    if tmpl is not None:
        row.qa_signer = tmpl.qa_signer_default
    for it in md.items:
        row.items.append(AtrDeliveryItem(
            pos=it.pos, supplier_article_code=it.supplier_article_code,
            part_number=it.part_number, part_number_norm=it.part_number_norm,
            matched_part_id=it.matched_part_id, part_name=it.part_name,
            drawing_number_issue=it.drawing_number_issue, category=it.category,
            qty=it.qty, weight_kg=it.weight_kg, po_pos=it.po_pos,
            match_status=it.match_status, row_order=it.row_order,
            serial_numbers=", ".join(it.serials) if it.serials else None,
        ))
    db.add(row)
    await db.commit()
    # Re-fetch with items eagerly loaded to avoid greenlet errors during serialization.
    return await _get(db, row.id)


async def _get(db: AsyncSession, delivery_id: int) -> AtrDelivery:
    row = (await db.execute(
        select(AtrDelivery)
        .options(selectinload(AtrDelivery.items))
        .where(AtrDelivery.id == delivery_id)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "delivery not found")
    return row


@router.post("/upload", response_model=AtrDeliveryRead, status_code=201)
async def upload(file: UploadFile = File(...),
                 db: AsyncSession = Depends(get_async_db_session)) -> AtrDelivery:
    raw = await file.read()
    try:
        parsed = await parse_lieferschein(raw)
    except ValueError as exc:
        raise HTTPException(400, f"could not read PDF: {exc}") from exc
    if not parsed.positions:
        raise HTTPException(422, "no positions found in Lieferschein")
    md = await match_positions(db, parsed, file.filename or "lieferschein.pdf")
    return await _persist_draft(db, md)


async def _smb_cfg(db):
    from app.models import AppSettings
    from app.services import atr_fileserver as fs
    row = (await db.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one()
    return fs.smb_config_from_settings(row), row


@router.get("/input-files")
async def input_files(db: AsyncSession = Depends(get_async_db_session)) -> dict:
    import asyncio
    from app.services import atr_fileserver as fs
    cfg, _ = await _smb_cfg(db)
    if cfg is None:
        return {"configured": False, "files": []}
    try:
        files = await asyncio.to_thread(fs.list_input_pdfs, cfg)
    except fs.AtrFileserverError as exc:
        raise HTTPException(502, f"fileserver error: {exc}") from exc
    return {"configured": True, "files": files}


@router.post("/input-files/process", response_model=AtrDeliveryRead, status_code=201)
async def process_input_file(payload: dict,
                             db: AsyncSession = Depends(get_async_db_session)) -> AtrDelivery:
    import asyncio
    from app.services import atr_fileserver as fs
    cfg, _ = await _smb_cfg(db)
    if cfg is None:
        raise HTTPException(400, "SMB fileserver not configured")
    name = Path(str(payload.get("filename", ""))).name
    if not name.lower().endswith(".pdf"):
        raise HTTPException(404, "file not found")
    try:
        raw = await asyncio.to_thread(fs.read_input, cfg, name)
    except fs.AtrFileserverError as exc:
        raise HTTPException(502, f"fileserver error: {exc}") from exc
    try:
        parsed = await parse_lieferschein(raw)
    except ValueError as exc:
        raise HTTPException(400, f"could not read PDF: {exc}") from exc
    if not parsed.positions:
        raise HTTPException(422, "no positions found in Lieferschein")
    md = await match_positions(db, parsed, name)
    delivery = await _persist_draft(db, md)
    # mark origin = scan + source_path
    delivery.origin = "scan"
    delivery.source_path = f"{cfg.input_path}/{name}"
    await db.commit()
    return await _get(db, delivery.id)


@router.get("", response_model=list[AtrDeliverySummary])
async def list_deliveries(db: AsyncSession = Depends(get_async_db_session)) -> list[AtrDelivery]:
    return list((await db.execute(
        select(AtrDelivery).order_by(AtrDelivery.id.desc())
    )).scalars().all())


@router.get("/next-atr-number")
async def next_atr_number(db: AsyncSession = Depends(get_async_db_session)) -> dict:
    """Suggested next running ATR number for the review mask (null to seed
    manually). Declared before /{delivery_id} so it isn't parsed as an id."""
    from app.services.atr_deliver import compute_next_atr_number
    return {"next": await compute_next_atr_number(db)}


@router.get("/{delivery_id}", response_model=AtrDeliveryRead)
async def get_delivery(delivery_id: int,
                       db: AsyncSession = Depends(get_async_db_session)) -> AtrDelivery:
    return await _get(db, delivery_id)


@router.patch("/{delivery_id}", response_model=AtrDeliveryRead)
async def patch_delivery(delivery_id: int, payload: AtrDeliveryUpdate,
                         db: AsyncSession = Depends(get_async_db_session)) -> AtrDelivery:
    row = await _get(db, delivery_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return await _get(db, delivery_id)


@router.delete("/{delivery_id}", status_code=204)
async def delete_delivery(delivery_id: int,
                          db: AsyncSession = Depends(get_async_db_session)) -> Response:
    """Delete a delivery and its items (failed attempts / old tests). Items
    cascade via the ORM relationship + FK ON DELETE CASCADE."""
    row = await _get(db, delivery_id)
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)


@router.patch("/{delivery_id}/items/{item_id}", response_model=AtrDeliveryItemRead)
async def patch_item(delivery_id: int, item_id: int, payload: AtrDeliveryItemUpdate,
                     db: AsyncSession = Depends(get_async_db_session)) -> AtrDeliveryItem:
    row = (await db.execute(
        select(AtrDeliveryItem).where(
            AtrDeliveryItem.id == item_id, AtrDeliveryItem.delivery_id == delivery_id)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "item not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await db.commit()
    await db.refresh(row)
    return row


# kind -> (media_type, base-name suffix, extension). The base name is built
# per-delivery (delivery_filename_base); the suffix distinguishes the docx.
_MEDIA = {
    "atr_xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "", ".xlsx"),
    "atr_pdf": ("application/pdf", "", ".pdf"),
    "label_docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                   "_Container", ".docx"),
}


@router.post("/{delivery_id}/generate", response_model=AtrGenerateManifest)
async def generate(delivery_id: int,
                   db: AsyncSession = Depends(get_async_db_session)) -> AtrGenerateManifest:
    from app.models import AppSettings
    from app.services.atr_deliver import generate_and_deliver
    row = await _get(db, delivery_id)
    settings_row = (await db.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one()
    try:
        return await generate_and_deliver(db, row, settings_row)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# Server destinations for "save to server", all under \\<host>\<share> (= Z:\).
# {year}/{kw} are filled per save; folders (incl. year/calendar-week) are created
# on demand. `kind` selects which generated artifact goes where.
def _server_targets(is_a380: bool) -> list[tuple[str, str, str]]:
    """Destinations for a delivery. Only the Excel Acceptance-Test-Report target
    is programme-specific (A350 vs A380 sub-folder + year-folder name); the two
    PDF targets carry no A350/A380 marker and are shared. Add the next
    destination by appending one tuple."""
    prog = "A380" if is_a380 else "A350"
    # NB: the A380 year folder is literally "ACM_ATR_A 380_....." (with a space);
    # {year} stays literal here and is filled later via str.format.
    year_folder = "ACM_ATR_A 380_.....{year}" if is_a380 else "ACM_ATR_A350_.....{year}"
    return [
        ("atr_xlsx",
         rf"1300 - Qualität\1320_QS\132002_WA-Prüfung\132002_02_TR_Spec_QAA\DIEHL\{prog}"
         rf"\ATR_Acceptance Test Report\{year_folder}",
         f"QS – Acceptance Test Report ({prog})"),
        ("atr_pdf",
         r"1200 - Logistik\Versand\ATR`S_Weight Reports_Firma Diehl_Portal",
         "Logistik – Versand"),
        ("atr_pdf",
         r"1300 - Qualität\1320_QS\132002_WA-Prüfung\132002_02_TR_Spec_QAA\DIEHL"
         r"\Weight Report für Firma Diehl ( verschicken )\{year}\KW {kw:02d}",
         "QS – Weight Report (verschicken)"),
    ]


@router.post("/{delivery_id}/save-to-server")
async def save_to_server(delivery_id: int,
                         db: AsyncSession = Depends(get_async_db_session)) -> dict:
    """Write the generated ATR to the fixed Diehl server folders (Excel + PDF).
    Year/calendar-week folders are created automatically; duplicates get a
    running ` (n)` suffix. Returns per-destination success/failure."""
    import asyncio
    from datetime import date

    from app.models import AppSettings
    from app.services import atr_fileserver as fs
    from app.services.atr_deliver import delivery_filename_base

    row = await _get(db, delivery_id)
    if not row.atr_xlsx or not row.atr_pdf:
        raise HTTPException(400, "ATR not generated yet")
    settings_row = (await db.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one()
    cfg = fs.smb_credentials_from_settings(settings_row)
    if cfg is None:
        raise HTTPException(400, "SMB-Zugangsdaten sind nicht konfiguriert")

    base = delivery_filename_base(row, list(row.items))
    today = date.today()
    fmt = {"year": today.year, "kw": today.isocalendar()[1]}
    payload = {"atr_xlsx": (bytes(row.atr_xlsx), ".xlsx"),
               "atr_pdf": (bytes(row.atr_pdf), ".pdf")}

    saved: list[dict] = []
    failed: list[dict] = []
    for kind, tmpl, label in _server_targets("380" in (row.ac_programme or "")):
        data, ext = payload[kind]
        rel_path = tmpl.format(**fmt)
        try:
            written = await asyncio.to_thread(fs.write_file, cfg, rel_path, f"{base}{ext}", data)
            saved.append({"label": label, "path": rel_path, "filename": written})
        except fs.AtrFileserverError as exc:
            log.warning("atr save-to-server failed [%s] for delivery %s: %s", label, delivery_id, exc)
            failed.append({"label": label, "error": str(exc)})
    return {"saved": saved, "failed": failed}


@router.get("/{delivery_id}/files/{kind}")
async def download(delivery_id: int, kind: str,
                   db: AsyncSession = Depends(get_async_db_session)) -> Response:
    if kind not in _MEDIA:
        raise HTTPException(404, "unknown file kind")
    from urllib.parse import quote

    from app.services.atr_deliver import delivery_filename_base

    row = await _get(db, delivery_id)
    data = {"atr_xlsx": row.atr_xlsx, "atr_pdf": row.atr_pdf, "label_docx": row.label_docx}[kind]
    if not data:
        raise HTTPException(404, "file not generated")
    media_type, suffix, ext = _MEDIA[kind]
    fname = f"{delivery_filename_base(row, list(row.items))}{suffix}{ext}"
    disp = f"attachment; filename=\"{fname}\"; filename*=UTF-8''{quote(fname)}"
    return Response(content=bytes(data), media_type=media_type,
                    headers={"Content-Disposition": disp})
