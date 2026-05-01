"""Manual sales-rep alias CRUD (admin-only).

Canonical alias rows (created by the Personio sync hook) are read-only
from this surface — DELETE returns 409 against them. To remove a
canonical row the admin must reconfigure ``personio_sales_dept`` so
the employee no longer qualifies on the next sync.

GET returns the full alias list; the HR settings page renders both
canonical (read-only, padlock) and manual rows from this single payload.

Compute-justified: clause 4 (admin-only mutation surface that bridges
the Kontakte file's ``Wer`` token to a Personio employee — Directus has
no equivalent shape because the join is computed at sync time).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import PersonioEmployee, SalesEmployeeAlias
from app.schemas import SalesAliasCreate, SalesAliasRead
from app.security.directus_auth import get_current_user, require_admin

router = APIRouter(
    prefix="/api/admin",
    dependencies=[Depends(get_current_user), Depends(require_admin)],
    tags=["sales-aliases"],
)


@router.get("/sales-aliases", response_model=list[SalesAliasRead])
async def list_aliases(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[SalesAliasRead]:
    rows = (
        await db.execute(select(SalesEmployeeAlias).order_by(SalesEmployeeAlias.id))
    ).scalars().all()
    return [SalesAliasRead.model_validate(r, from_attributes=True) for r in rows]


@router.post("/sales-aliases", response_model=SalesAliasRead, status_code=201)
async def create_alias(
    payload: SalesAliasCreate,
    db: AsyncSession = Depends(get_async_db_session),
) -> SalesAliasRead:
    emp = await db.get(PersonioEmployee, payload.personio_employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="personio employee not found")
    token = payload.employee_token.upper()
    existing = (
        await db.execute(
            select(SalesEmployeeAlias).where(
                SalesEmployeeAlias.employee_token == token
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="token already mapped")
    alias = SalesEmployeeAlias(
        personio_employee_id=payload.personio_employee_id,
        employee_token=token,
        is_canonical=False,
    )
    db.add(alias)
    await db.commit()
    await db.refresh(alias)
    return SalesAliasRead.model_validate(alias, from_attributes=True)


@router.delete("/sales-aliases/{alias_id}", status_code=204)
async def delete_alias(
    alias_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    alias = await db.get(SalesEmployeeAlias, alias_id)
    if alias is None:
        raise HTTPException(status_code=404, detail="alias not found")
    if alias.is_canonical:
        raise HTTPException(
            status_code=409,
            detail=(
                "canonical aliases are managed by the Personio sync; remove "
                "the employee from the sales department instead"
            ),
        )
    await db.delete(alias)
    await db.commit()
