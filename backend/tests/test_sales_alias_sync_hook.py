"""Personio sync hook — rebuild canonical sales aliases."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select, update

from app.database import AsyncSessionLocal
from app.models import (
    AppSettings,
    PersonioEmployee,
    SalesEmployeeAlias,
)
from app.services.hr_sync import rebuild_canonical_sales_aliases

pytestmark = pytest.mark.asyncio


async def _wipe() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(SalesEmployeeAlias))
        await s.execute(
            delete(PersonioEmployee).where(PersonioEmployee.id.in_([90001, 90002]))
        )
        await s.execute(
            update(AppSettings)
            .where(AppSettings.id == 1)
            .values(personio_sales_dept=None)
        )
        await s.commit()


async def test_rebuild_creates_canonical_for_sales_dept_employees():
    await _wipe()
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(AppSettings)
            .where(AppSettings.id == 1)
            .values(personio_sales_dept=["Vertrieb"])
        )
        s.add(
            PersonioEmployee(
                id=90001,
                last_name="Müller",
                department="Vertrieb",
                synced_at=datetime.now(timezone.utc),
            )
        )
        s.add(
            PersonioEmployee(
                id=90002,
                last_name="Schmidt",
                department="Production",
                synced_at=datetime.now(timezone.utc),
            )
        )
        await s.commit()

        await rebuild_canonical_sales_aliases(s)

        aliases = (
            await s.execute(
                select(SalesEmployeeAlias).where(
                    SalesEmployeeAlias.personio_employee_id.in_([90001, 90002])
                )
            )
        ).scalars().all()
        canonical = [a for a in aliases if a.is_canonical]
        tokens = {a.employee_token for a in canonical}
        # Only the Vertrieb employee got a canonical alias.
        assert tokens == {"MUELLER"}


async def test_rebuild_preserves_manual_aliases():
    await _wipe()
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(AppSettings)
            .where(AppSettings.id == 1)
            .values(personio_sales_dept=["Vertrieb"])
        )
        s.add(
            PersonioEmployee(
                id=90001,
                last_name="Müller",
                department="Vertrieb",
                synced_at=datetime.now(timezone.utc),
            )
        )
        s.add(
            SalesEmployeeAlias(
                personio_employee_id=90001,
                employee_token="GUENNI",
                is_canonical=False,
            )
        )
        await s.commit()

        await rebuild_canonical_sales_aliases(s)

        aliases = (
            await s.execute(
                select(SalesEmployeeAlias).where(
                    SalesEmployeeAlias.personio_employee_id == 90001
                )
            )
        ).scalars().all()
        pairs = {(a.employee_token, a.is_canonical) for a in aliases}
        # Manual row preserved; canonical added.
        assert ("GUENNI", False) in pairs
        assert ("MUELLER", True) in pairs


async def test_rebuild_drops_canonical_when_dept_config_empty():
    await _wipe()
    async with AsyncSessionLocal() as s:
        s.add(
            PersonioEmployee(
                id=90001,
                last_name="Müller",
                department="Vertrieb",
                synced_at=datetime.now(timezone.utc),
            )
        )
        s.add(
            SalesEmployeeAlias(
                personio_employee_id=90001,
                employee_token="MUELLER",
                is_canonical=True,
            )
        )
        await s.commit()

        await rebuild_canonical_sales_aliases(s)

        rows = (
            await s.execute(
                select(SalesEmployeeAlias).where(
                    SalesEmployeeAlias.personio_employee_id == 90001
                )
            )
        ).scalars().all()
        assert rows == []  # canonical was dropped, no manual rows existed
