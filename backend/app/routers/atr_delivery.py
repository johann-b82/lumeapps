"""/api/atr/deliveries/* — admin-gated Lieferschein ingest + review (Phase B).

Generation endpoints (Wave 2): POST /{id}/generate, GET /{id}/files/{kind}.
"""
from __future__ import annotations

import logging
import os
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
from app.security.directus_auth import get_current_user, require_admin
from app.services.atr_lieferschein import parse_lieferschein
from app.services.atr_match import MatchedDelivery, match_positions
from app.services.atr_generate_xlsx import build_atr_xlsx, convert_xlsx_to_pdf
from app.services.atr_generate_docx import build_containerbeschriftung

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/atr/deliveries", tags=["atr"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
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
        ac_programme=md.ac_programme, compartment=md.compartment, msn=md.msn,
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


@router.get("/input-files")
async def input_files() -> dict:
    d = os.environ.get("ATR_INPUT_DIR")
    if not d or not Path(d).is_dir():
        return {"configured": False, "files": []}
    files = sorted(p.name for p in Path(d).glob("*.pdf") if p.is_file())
    return {"configured": True, "files": files}


@router.post("/input-files/process", response_model=AtrDeliveryRead, status_code=201)
async def process_input_file(payload: dict,
                             db: AsyncSession = Depends(get_async_db_session)) -> AtrDelivery:
    d = os.environ.get("ATR_INPUT_DIR")
    if not d or not Path(d).is_dir():
        raise HTTPException(400, "ATR_INPUT_DIR not configured")
    name = payload.get("filename", "")
    # path-traversal guard: basename only, must exist in the dir
    safe = Path(name).name
    target = Path(d) / safe
    if safe != name or not target.is_file() or target.suffix.lower() != ".pdf":
        raise HTTPException(404, "file not found in input directory")
    try:
        parsed = await parse_lieferschein(target.read_bytes())
    except ValueError as exc:
        raise HTTPException(400, f"could not read PDF: {exc}") from exc
    if not parsed.positions:
        raise HTTPException(422, "no positions found in Lieferschein")
    md = await match_positions(db, parsed, safe)
    return await _persist_draft(db, md)


@router.get("", response_model=list[AtrDeliverySummary])
async def list_deliveries(db: AsyncSession = Depends(get_async_db_session)) -> list[AtrDelivery]:
    return list((await db.execute(
        select(AtrDelivery).order_by(AtrDelivery.id.desc())
    )).scalars().all())


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


_MEDIA = {
    "atr_xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "atr.xlsx"),
    "atr_pdf": ("application/pdf", "atr.pdf"),
    "label_docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                   "containerbeschriftung.docx"),
}


@router.post("/{delivery_id}/generate", response_model=AtrGenerateManifest)
async def generate(delivery_id: int,
                   db: AsyncSession = Depends(get_async_db_session)) -> AtrGenerateManifest:
    row = await _get(db, delivery_id)
    items = list(row.items)
    tmpl = (await db.execute(select(AtrTemplate).where(AtrTemplate.id == 1))).scalar_one_or_none()
    if tmpl is None or tmpl.structure_xlsx is None:
        raise HTTPException(400, "no structural template set (upload one in ATR → Template)")

    warnings: list[str] = []
    xlsx = build_atr_xlsx(tmpl.structure_xlsx, row, items)
    docx = build_containerbeschriftung(row, items)
    pdf: bytes | None = None
    try:
        pdf = await convert_xlsx_to_pdf(xlsx)
    except Exception as exc:  # noqa: BLE001 — never lose xlsx/docx over the PDF step
        log.warning("atr generate: pdf conversion failed for delivery %s: %s", delivery_id, exc)
        warnings.append("PDF conversion failed; the .xlsx and .docx are still available.")

    row.atr_xlsx = xlsx
    row.atr_pdf = pdf
    row.label_docx = docx
    row.status = "generated"
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()

    files = ["atr_xlsx", "label_docx"] + (["atr_pdf"] if pdf else [])
    unmatched = sum(1 for i in items if i.match_status != "matched")
    if unmatched:
        warnings.append(f"{unmatched} unmatched part(s) marked red in the ATR — fix in Excel.")
    return AtrGenerateManifest(delivery_id=delivery_id, files=files,
                               pdf_available=pdf is not None,
                               unmatched_count=unmatched, warnings=warnings)


@router.get("/{delivery_id}/files/{kind}")
async def download(delivery_id: int, kind: str,
                   db: AsyncSession = Depends(get_async_db_session)) -> Response:
    if kind not in _MEDIA:
        raise HTTPException(404, "unknown file kind")
    row = await _get(db, delivery_id)
    data = {"atr_xlsx": row.atr_xlsx, "atr_pdf": row.atr_pdf, "label_docx": row.label_docx}[kind]
    if not data:
        raise HTTPException(404, "file not generated")
    media_type, fname = _MEDIA[kind]
    return Response(content=bytes(data), media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})
