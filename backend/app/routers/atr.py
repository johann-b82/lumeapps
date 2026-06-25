"""/api/atr/* — admin-gated ATR reference catalog + template (Phase A).

Router-level admin gate: every endpoint requires Admin. The dep-audit test
in tests/test_atr_admin_gate.py enforces this.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import File, Form, UploadFile

from app.database import get_async_db_session
from app.models import AtrPart, AtrTemplate
from app.schemas import (
    AtrImportPartPreview,
    AtrImportPreview,
    AtrImportResult,
    AtrPartCreate,
    AtrPartRead,
    AtrPartUpdate,
    AtrTemplateRead,
    AtrTemplateUpdate,
)
from app.security.directus_auth import get_current_user, require_admin
from app.services.atr_reference_import import ParsedWorkbook, norm_partno, parse_workbook

router = APIRouter(
    prefix="/api/atr",
    tags=["atr"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)


@router.get("/parts", response_model=list[AtrPartRead])
async def list_parts(
    search: str | None = None,
    category: str | None = None,
    limit: int = 500,
    offset: int = 0,
    db: AsyncSession = Depends(get_async_db_session),
) -> list[AtrPart]:
    stmt = select(AtrPart)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(
            AtrPart.part_number.ilike(like),
            AtrPart.part_name.ilike(like),
            AtrPart.supplier_article_code.ilike(like),
        ))
    if category:
        stmt = stmt.where(AtrPart.category == category)
    stmt = stmt.order_by(AtrPart.part_number).limit(min(limit, 2000)).offset(offset)
    return list((await db.execute(stmt)).scalars().all())


@router.get("/parts/{part_id}", response_model=AtrPartRead)
async def get_part(
    part_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> AtrPart:
    row = (await db.execute(select(AtrPart).where(AtrPart.id == part_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "part not found")
    return row


@router.post("/parts", response_model=AtrPartRead, status_code=201)
async def create_part(
    payload: AtrPartCreate, db: AsyncSession = Depends(get_async_db_session)
) -> AtrPart:
    now = datetime.now(timezone.utc)
    row = AtrPart(
        part_number=payload.part_number,
        part_number_norm=norm_partno(payload.part_number),
        supplier_article_code=payload.supplier_article_code,
        part_name=payload.part_name,
        drawing_number_issue=payload.drawing_number_issue,
        default_weight_kg=payload.default_weight_kg,
        qty=payload.qty,
        category=payload.category,
        po_pos=payload.po_pos,
        source_filename="(manual)",
        imported_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "a part with this part number already exists") from exc
    await db.refresh(row)
    return row


@router.patch("/parts/{part_id}", response_model=AtrPartRead)
async def update_part(
    part_id: int, payload: AtrPartUpdate,
    db: AsyncSession = Depends(get_async_db_session),
) -> AtrPart:
    row = (await db.execute(select(AtrPart).where(AtrPart.id == part_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "part not found")
    data = payload.model_dump(exclude_unset=True)
    if "part_number" in data and data["part_number"]:
        row.part_number_norm = norm_partno(data["part_number"])
    for k, v in data.items():
        setattr(row, k, v)
    row.updated_at = datetime.now(timezone.utc)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "part number conflict") from exc
    await db.refresh(row)
    return row


@router.delete("/parts/{part_id}", status_code=204)
async def delete_part(
    part_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> None:
    result = await db.execute(delete(AtrPart).where(AtrPart.id == part_id))
    if result.rowcount == 0:
        raise HTTPException(404, "part not found")
    await db.commit()


def _template_read(tmpl: AtrTemplate) -> AtrTemplateRead:
    return AtrTemplateRead(
        id=tmpl.id, customer=tmpl.customer, ac_programme=tmpl.ac_programme,
        work_package=tmpl.work_package, purchaser_spec=tmpl.purchaser_spec,
        atp=tmpl.atp, supplier_spec=tmpl.supplier_spec, reference_no=tmpl.reference_no,
        supplier=tmpl.supplier, customer_spec=tmpl.customer_spec,
        nscm_code=tmpl.nscm_code, ata_chapter=tmpl.ata_chapter,
        weighing_equipment=tmpl.weighing_equipment,
        qa_signer_default=tmpl.qa_signer_default,
        structure_filename=tmpl.structure_filename,
        has_structure=tmpl.structure_xlsx is not None,
        updated_at=tmpl.updated_at,
    )


@router.get("/template", response_model=AtrTemplateRead)
async def get_template(db: AsyncSession = Depends(get_async_db_session)) -> AtrTemplateRead:
    tmpl = (await db.execute(select(AtrTemplate).where(AtrTemplate.id == 1))).scalar_one()
    return _template_read(tmpl)


@router.patch("/template", response_model=AtrTemplateRead)
async def patch_template(
    payload: AtrTemplateUpdate, db: AsyncSession = Depends(get_async_db_session)
) -> AtrTemplateRead:
    tmpl = (await db.execute(select(AtrTemplate).where(AtrTemplate.id == 1))).scalar_one()
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tmpl, k, v)
    tmpl.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tmpl)
    return _template_read(tmpl)


@router.post("/template/structure", response_model=AtrTemplateRead)
async def set_template_structure(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db_session),
) -> AtrTemplateRead:
    raw = await file.read()
    try:
        parse_workbook(raw, file.filename or "structure.xlsx")  # validate it parses
    except ValueError as exc:
        raise HTTPException(400, f"{file.filename}: {exc}") from exc
    tmpl = (await db.execute(select(AtrTemplate).where(AtrTemplate.id == 1))).scalar_one()
    tmpl.structure_xlsx = raw
    tmpl.structure_filename = file.filename
    tmpl.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tmpl)
    return _template_read(tmpl)


def _header_dict(pw: ParsedWorkbook) -> dict:
    h = pw.header
    return {
        "customer": h.customer, "ac_programme": h.ac_programme,
        "work_package": h.work_package, "purchaser_spec": h.purchaser_spec,
        "atp": h.atp, "supplier_spec": h.supplier_spec,
        "reference_no": h.reference_no, "supplier": h.supplier,
        "customer_spec": h.customer_spec, "nscm_code": h.nscm_code,
        "ata_chapter": h.ata_chapter, "weighing_equipment": h.weighing_equipment,
    }


def _norm_weight(w):
    return None if w is None else Decimal(w).quantize(Decimal("0.001"))


def _value_fields(part) -> tuple:
    """The fields an import overwrites — used to classify new/updated/unchanged."""
    return (
        part.supplier_article_code, part.part_name, part.drawing_number_issue,
        _norm_weight(part.default_weight_kg), part.qty, part.category,
    )


@router.post("/import/preview", response_model=list[AtrImportPreview])
async def import_preview(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[AtrImportPreview]:
    existing = {
        p.part_number_norm: p
        for p in (await db.execute(select(AtrPart))).scalars().all()
    }
    out: list[AtrImportPreview] = []
    for f in files:
        raw = await f.read()
        try:
            pw = parse_workbook(raw, f.filename or "upload.xlsx")
        except ValueError as exc:
            raise HTTPException(400, f"{f.filename}: {exc}") from exc
        parts, new, upd, unch = [], 0, 0, 0
        for p in pw.parts:
            prev = existing.get(p.part_number_norm)
            if prev is None:
                status = "new"; new += 1
            elif _value_fields(prev) != _value_fields(p):
                status = "updated"; upd += 1
            else:
                status = "unchanged"; unch += 1
            parts.append(AtrImportPartPreview(
                part_number=p.part_number, part_number_norm=p.part_number_norm,
                supplier_article_code=p.supplier_article_code, part_name=p.part_name,
                drawing_number_issue=p.drawing_number_issue,
                default_weight_kg=p.default_weight_kg, qty=p.qty,
                category=p.category, status=status,
            ))
        out.append(AtrImportPreview(
            source_filename=pw.source_filename, header=_header_dict(pw),
            parts=parts, new_count=new, updated_count=upd,
            unchanged_count=unch, warnings=pw.warnings,
        ))
    return out


@router.post("/import/commit", response_model=list[AtrImportResult])
async def import_commit(
    files: list[UploadFile] = File(...),
    update_template: bool = Form(default=False),
    set_structure: bool = Form(default=False),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[AtrImportResult]:
    now = datetime.now(timezone.utc)
    results: list[AtrImportResult] = []
    for f in files:
        raw = await f.read()
        try:
            pw = parse_workbook(raw, f.filename or "upload.xlsx")
        except ValueError as exc:
            raise HTTPException(400, f"{f.filename}: {exc}") from exc
        existing = {
            p.part_number_norm: p
            for p in (await db.execute(select(AtrPart))).scalars().all()
        }
        created = updated = 0
        for p in pw.parts:
            prev = existing.get(p.part_number_norm)
            if prev is None:
                db.add(AtrPart(
                    part_number=p.part_number, part_number_norm=p.part_number_norm,
                    supplier_article_code=p.supplier_article_code,
                    part_name=p.part_name, drawing_number_issue=p.drawing_number_issue,
                    default_weight_kg=p.default_weight_kg, qty=p.qty,
                    category=p.category, po_pos=None,
                    source_filename=pw.source_filename, imported_at=now, updated_at=now,
                ))
                created += 1
            else:
                prev.supplier_article_code = p.supplier_article_code
                prev.part_name = p.part_name
                prev.drawing_number_issue = p.drawing_number_issue
                prev.default_weight_kg = p.default_weight_kg
                prev.qty = p.qty
                prev.category = p.category
                prev.source_filename = pw.source_filename
                prev.imported_at = now
                prev.updated_at = now
                updated += 1

        template_updated = False
        structure_set = False
        if update_template or set_structure:
            tmpl = (await db.execute(select(AtrTemplate).where(AtrTemplate.id == 1))).scalar_one()
            if update_template:
                for k, v in _header_dict(pw).items():
                    setattr(tmpl, k, v)
                tmpl.updated_at = now
                template_updated = True
            if set_structure:
                tmpl.structure_xlsx = raw
                tmpl.structure_filename = pw.source_filename
                tmpl.updated_at = now
                structure_set = True

        await db.commit()
        results.append(AtrImportResult(
            source_filename=pw.source_filename, created=created, updated=updated,
            template_updated=template_updated, structure_set=structure_set,
            warnings=pw.warnings,
        ))
    return results
