"""/api/atr/* — admin-gated ATR reference catalog + template (Phase A).

Router-level admin gate: every endpoint requires Admin. The dep-audit test
in tests/test_atr_admin_gate.py enforces this.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import AtrPart
from app.schemas import AtrPartCreate, AtrPartRead, AtrPartUpdate
from app.security.directus_auth import get_current_user, require_admin
from app.services.atr_reference_import import norm_partno

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
