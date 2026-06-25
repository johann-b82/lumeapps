# ATR Phase A — Reference Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `atr` module to LumeApps that imports the Diehl ATR reference workbooks into one editable global parts catalog plus a single structural-template singleton, with an admin UI to view/edit/import.

**Architecture:** New FastAPI module (`models/atr.py`, `schemas/atr.py`, `services/atr_reference_import.py`, `routers/atr.py`) behind a router-level admin gate, one Alembic migration creating `atr_part` (unique `part_number_norm`) + `atr_template` (singleton). An openpyxl parser turns each uploaded `.xlsx` into header defaults + parts; a preview→commit flow upserts parts by `part_number_norm`. React pages (catalog, import, template) under the existing wouter shell, reached from an admin-only launcher tile.

**Tech Stack:** FastAPI 0.135.3 · SQLAlchemy 2.0.49 (async) · Pydantic v2 · openpyxl 3.1.5 · Alembic 1.18.4 · React 19 · Vite · TanStack Query 5 · wouter · shadcn/ui · react-i18next.

Reference spec: `docs/superpowers/specs/2026-06-25-atr-reference-foundation-design.md`.

## Global Constraints

- **Admin-only module.** Every `/api/atr/*` route is gated at the router level with `dependencies=[Depends(get_current_user), Depends(require_admin)]` (mirror `backend/app/routers/sensors.py`). The CI dep-audit (`backend/tests/test_admin_gate_audit.py`) enforces this.
- **Migration head:** new migration `v1_63_atr_reference` with `down_revision = "v1_62_tippspiel"` (current head — re-verify with `cd backend && alembic heads` before writing).
- **⚠ TEST DB SAFETY:** backend pytest DELETEs whole tables and, if real `POSTGRES_*` env vars point at the live `acm_kpi` DB, will wipe production data. Run backend tests **only** against a disposable database — set `POSTGRES_DB` to a throwaway value (e.g. `acm_test`) or run in the dedicated test container. Never run pytest in a shell that has the production `.env` exported.
- **Decimals on the wire are strings.** Pydantic serializes `Numeric`/`Decimal` as JSON strings; TypeScript types use `string` and parse with `Number(...)` at render — never store as `number`.
- **German i18n required.** Primary users are German-speaking QA: every UI string gets both `en.json` and `de.json` keys under the `atr.*` namespace.
- **part_number_norm** = digits-only of the raw part number (`"VR11S 1010 048 000"` → `"111010048000"`). It is the catalog's unique key and the Phase-B match key.
- **Commit after every task.** Conventional-commit messages; co-author trailer as configured.

---

## File Structure

**Backend**
- Create `backend/app/models/atr.py` — `AtrPart`, `AtrTemplate` ORM.
- Modify `backend/app/models/__init__.py` — register both.
- Create `backend/app/schemas/atr.py` — Pydantic DTOs.
- Modify `backend/app/schemas/__init__.py` — re-export.
- Create `backend/alembic/versions/v1_63_atr_reference.py` — migration.
- Create `backend/app/services/atr_reference_import.py` — parser.
- Create `backend/app/routers/atr.py` — router.
- Modify `backend/app/main.py` — include router.
- Create `backend/tests/_atr_fixtures.py` — in-memory workbook builder.
- Create `backend/tests/test_atr_reference_import.py`, `test_atr_router.py`, `test_atr_merge.py`, `test_atr_admin_gate.py`.

**Frontend**
- Create `frontend/src/lib/atrApi.ts` — types + fetchers.
- Create `frontend/src/pages/AtrPartsPage.tsx`, `AtrImportPage.tsx`, `AtrTemplatePage.tsx`.
- Modify `frontend/src/App.tsx` — routes.
- Modify `frontend/src/pages/LauncherPage.tsx` — admin tile.
- Modify `frontend/src/locales/en.json`, `frontend/src/locales/de.json` — `atr.*` keys.
- Create `frontend/src/pages/__tests__/AtrImportPage.test.tsx`.

---

## Task 1: ORM models + migration

**Files:**
- Create: `backend/app/models/atr.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/v1_63_atr_reference.py`
- Test: `backend/tests/test_atr_models.py`

**Interfaces:**
- Produces: `AtrPart` (table `atr_part`), `AtrTemplate` (table `atr_template`), both importable from `app.models`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_models.py
from app.models import AtrPart, AtrTemplate
from app.database import Base


def test_atr_tables_registered():
    assert "atr_part" in Base.metadata.tables
    assert "atr_template" in Base.metadata.tables


def test_atr_part_columns():
    cols = {c.name for c in AtrPart.__table__.columns}
    assert {
        "id", "part_number", "part_number_norm", "supplier_article_code",
        "part_name", "drawing_number_issue", "default_weight_kg", "qty",
        "category", "po_pos", "source_filename", "imported_at", "updated_at",
    } <= cols
    assert AtrPart.__table__.c.part_number_norm.unique is True


def test_atr_template_is_singleton():
    names = {c.name for c in AtrTemplate.__table__.constraints}
    assert "ck_atr_template_singleton" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest backend/tests/test_atr_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'AtrPart'`.

- [ ] **Step 3: Write the models**

```python
# backend/app/models/atr.py
"""ATR module ORM — global parts catalog + single structural template.

Phase A of the ATR roadmap (see
docs/superpowers/specs/2026-06-25-atr-reference-foundation-design.md).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AtrPart(Base):
    """One row per distinct part (by part_number_norm). The full editable catalog."""
    __tablename__ = "atr_part"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_number: Mapped[str] = mapped_column(String(60), nullable=False)
    part_number_norm: Mapped[str] = mapped_column(
        String(40), nullable=False, unique=True, index=True
    )
    supplier_article_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    part_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    drawing_number_issue: Mapped[str | None] = mapped_column(String(60), nullable=True)
    default_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    po_pos: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AtrTemplate(Base):
    """Singleton (id=1): editable header-block defaults + the stored structural workbook."""
    __tablename__ = "atr_template"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_atr_template_singleton"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    customer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ac_programme: Mapped[str | None] = mapped_column(String(100), nullable=True)
    work_package: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchaser_spec: Mapped[str | None] = mapped_column(String(200), nullable=True)
    atp: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supplier_spec: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reference_no: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_spec: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nscm_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ata_chapter: Mapped[str | None] = mapped_column(String(20), nullable=True)
    weighing_equipment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    qa_signer_default: Mapped[str | None] = mapped_column(String(100), nullable=True)
    structure_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    structure_xlsx: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

Then register in `backend/app/models/__init__.py`: add after the signage import block:

```python
# ATR module models (Phase A)
from app.models.atr import AtrPart, AtrTemplate  # noqa: F401
```

and add `"AtrPart", "AtrTemplate",` to the `__all__` list.

- [ ] **Step 4: Write the migration**

```python
# backend/alembic/versions/v1_63_atr_reference.py
"""v1.63: atr_part + atr_template (ATR reference foundation, Phase A)

Revision ID: v1_63_atr_reference
Revises: v1_62_tippspiel
Create Date: 2026-06-25
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "v1_63_atr_reference"
down_revision = "v1_62_tippspiel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "atr_part",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("part_number", sa.String(length=60), nullable=False),
        sa.Column("part_number_norm", sa.String(length=40), nullable=False),
        sa.Column("supplier_article_code", sa.String(length=40), nullable=True),
        sa.Column("part_name", sa.String(length=200), nullable=True),
        sa.Column("drawing_number_issue", sa.String(length=60), nullable=True),
        sa.Column("default_weight_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("qty", sa.Integer, nullable=False, server_default="1"),
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("po_pos", sa.String(length=20), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_atr_part_norm", "atr_part", ["part_number_norm"], unique=True
    )

    op.create_table(
        "atr_template",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("customer", sa.String(length=200), nullable=True),
        sa.Column("ac_programme", sa.String(length=100), nullable=True),
        sa.Column("work_package", sa.Text, nullable=True),
        sa.Column("purchaser_spec", sa.String(length=200), nullable=True),
        sa.Column("atp", sa.String(length=200), nullable=True),
        sa.Column("supplier_spec", sa.String(length=200), nullable=True),
        sa.Column("reference_no", sa.String(length=200), nullable=True),
        sa.Column("supplier", sa.String(length=200), nullable=True),
        sa.Column("customer_spec", sa.String(length=100), nullable=True),
        sa.Column("nscm_code", sa.String(length=40), nullable=True),
        sa.Column("ata_chapter", sa.String(length=20), nullable=True),
        sa.Column("weighing_equipment", sa.String(length=100), nullable=True),
        sa.Column("qa_signer_default", sa.String(length=100), nullable=True),
        sa.Column("structure_filename", sa.String(length=255), nullable=True),
        sa.Column("structure_xlsx", postgresql.BYTEA, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_atr_template_singleton"),
    )
    # Seed the singleton row (all-null defaults).
    op.execute(
        sa.text(
            "INSERT INTO atr_template (id, updated_at) VALUES (1, :ts)"
        ).bindparams(ts=datetime.now(timezone.utc))
    )


def downgrade() -> None:
    op.drop_table("atr_template")
    op.drop_index("ix_atr_part_norm", table_name="atr_part")
    op.drop_table("atr_part")
```

- [ ] **Step 5: Apply the migration**

Run: `docker compose exec -T api alembic upgrade head`
Expected: `Running upgrade v1_62_tippspiel -> v1_63_atr_reference`.

- [ ] **Step 6: Run the test to verify it passes**

Run: `docker compose exec -T api pytest backend/tests/test_atr_models.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/atr.py backend/app/models/__init__.py backend/alembic/versions/v1_63_atr_reference.py backend/tests/test_atr_models.py
git commit -m "feat(atr): atr_part + atr_template models and migration"
```

---

## Task 2: Workbook parser service

**Files:**
- Create: `backend/app/services/atr_reference_import.py`
- Create: `backend/tests/_atr_fixtures.py`
- Test: `backend/tests/test_atr_reference_import.py`

**Interfaces:**
- Produces:
  - `norm_partno(s: str) -> str` — digits-only.
  - `parse_workbook(file_bytes: bytes, source_filename: str) -> ParsedWorkbook`.
  - dataclasses `ParsedPart`, `ParsedHeader`, `ParsedWorkbook` (fields used by Task 5).
  - `build_atr_workbook_bytes(...)` test helper (consumed by Tasks 2, 5, 7).

- [ ] **Step 1: Write the fixture builder**

```python
# backend/tests/_atr_fixtures.py
"""In-memory ATR workbook builder for tests — avoids committing binaries."""
from io import BytesIO

from openpyxl import Workbook

DEFAULT_PARTS = [
    # (article_code, part_number, part_name, serial, drawing, qty, weight)
    ("6060", "VR11S 1010 016 000", "CARPET EMERGENCY EXIT HATCH", "N/A", "VR11S 1010-10/D", 1, "0.413"),
    ("11395", "VR11S 1010 048 000", "CARPET BEDS FWD", "N/A", "VR11S 1010-27/A", 1, "1.218"),
]


def build_atr_workbook_bytes(parts=None, visible_title="CCRC 6 BED",
                             set_title="SET 6 BED CCRC") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = visible_title
    ws["A1"] = "Customer:"
    ws["D1"] = "Diehl Aviation Laupheim GmbH"
    ws["D2"] = "A350 XWB"
    ws["A3"] = "Work Package:"
    ws["D3"] = "Soft Furnishing for Flight and Cabin Crew Rest Compartments"
    ws["G3"] = 25
    ws["D4"] = "PTS 2552 0015 01, Issue 02"
    ws["G4"] = "C9312"
    ws["D5"] = "ACM-A350CRC-ATP-002 Issue 02"
    ws["D6"] = "ACM-A350CRC-SES-003 Issue 03"
    ws["D7"] = "PA-CO-BTS-2010-042-01-CRC_Soft Furnishing"
    ws["D8"] = "ACM GmbH - Woringer Strasse 11 - 87700 Memmingen"
    ws["G8"] = "N/A"
    ws["A11"] = set_title
    ws["F12"] = "Plattenwaage PW015"
    headers = ["PO Pos", "Supplier Article Code", "Part Number / Index",
               "Part Name", "Serial Number", "Drawing Number / Issue",
               "Qty", "Weight [kg]"]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=13, column=i, value=h)
    ws["A14"] = "CARPET"
    rows = DEFAULT_PARTS if parts is None else parts
    r = 15
    for (art, pn, name, ser, draw, qty, wt) in rows:
        ws.cell(r, 2, art)
        ws.cell(r, 3, pn)
        ws.cell(r, 4, name)
        ws.cell(r, 5, ser)
        ws.cell(r, 6, draw)
        ws.cell(r, 7, qty)
        ws.cell(r, 8, wt)
        r += 1
    ws.cell(r + 1, 6, "Total weight")
    ws.cell(r + 1, 8, "1.631")
    wb.create_sheet("CCRC 8 BED").sheet_state = "hidden"
    wb.create_sheet("FCRC").sheet_state = "hidden"
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()
```

- [ ] **Step 2: Write the failing parser test**

```python
# backend/tests/test_atr_reference_import.py
from decimal import Decimal

import pytest

from app.services.atr_reference_import import norm_partno, parse_workbook
from tests._atr_fixtures import build_atr_workbook_bytes


def test_norm_partno_digits_only():
    assert norm_partno("VR11S 1010 048 000") == "111010048000"
    assert norm_partno("VR11S1010-027/A") == "1110100271"


def test_parse_header_and_parts():
    pw = parse_workbook(build_atr_workbook_bytes(), "demo.xlsx")
    assert pw.header.customer == "Diehl Aviation Laupheim GmbH"
    assert pw.header.ata_chapter == "25"
    assert pw.header.nscm_code == "C9312"
    assert len(pw.parts) == 2
    p = pw.parts[0]
    assert p.part_number == "VR11S 1010 016 000"
    assert p.part_number_norm == "111010016000"
    assert p.part_name == "CARPET EMERGENCY EXIT HATCH"
    assert p.drawing_number_issue == "VR11S 1010-10/D"
    assert p.category == "CARPET"
    assert p.default_weight_kg == Decimal("0.413")
    assert p.qty == 1


def test_parse_collects_weight_warning():
    parts = [("6060", "VR11S 1010 016 000", "X", "N/A", "VR11S 1010-10/D", 1, "not-a-number")]
    pw = parse_workbook(build_atr_workbook_bytes(parts=parts), "bad.xlsx")
    assert pw.parts[0].default_weight_kg is None
    assert any("weight" in w.lower() for w in pw.warnings)


def test_parse_rejects_multiple_visible_sheets():
    from openpyxl import Workbook
    from io import BytesIO
    wb = Workbook()
    wb.active.title = "one"
    wb.create_sheet("two")  # visible by default → two visible sheets
    bio = BytesIO(); wb.save(bio)
    with pytest.raises(ValueError):
        parse_workbook(bio.getvalue(), "two-visible.xlsx")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `docker compose exec -T api pytest backend/tests/test_atr_reference_import.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.atr_reference_import'`.

- [ ] **Step 4: Write the parser**

```python
# backend/app/services/atr_reference_import.py
"""Parse a Diehl ATR reference workbook into header defaults + parts.

Pure parsing, no DB. See the design spec's "Source-file analysis" for the
fixed cell map. Reads only the single VISIBLE sheet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import load_workbook


@dataclass
class ParsedPart:
    row_order: int
    category: str | None
    supplier_article_code: str | None
    part_number: str
    part_number_norm: str
    part_name: str | None
    serial_number: str | None
    drawing_number_issue: str | None
    qty: int
    default_weight_kg: Decimal | None


@dataclass
class ParsedHeader:
    customer: str | None = None
    ac_programme: str | None = None
    work_package: str | None = None
    purchaser_spec: str | None = None
    atp: str | None = None
    supplier_spec: str | None = None
    reference_no: str | None = None
    supplier: str | None = None
    customer_spec: str | None = None
    nscm_code: str | None = None
    ata_chapter: str | None = None
    weighing_equipment: str | None = None


@dataclass
class ParsedWorkbook:
    source_filename: str
    header: ParsedHeader
    parts: list[ParsedPart] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def norm_partno(s: str) -> str:
    return "".join(ch for ch in str(s) if ch.isdigit())


def _cell(ws, coord: str) -> str | None:
    v = ws[coord].value
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _to_decimal(v) -> Decimal | None:
    if v is None:
        return None
    s = str(v).strip().replace(",", ".")
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _to_int(v, default: int = 1) -> int:
    if v is None:
        return default
    try:
        return int(float(str(v).strip().replace(",", ".")))
    except (ValueError, TypeError):
        return default


def parse_workbook(file_bytes: bytes, source_filename: str) -> ParsedWorkbook:
    wb = load_workbook(BytesIO(file_bytes), data_only=True)
    visible = [ws for ws in wb.worksheets if ws.sheet_state == "visible"]
    if len(visible) != 1:
        raise ValueError(
            f"expected exactly one visible sheet, found {len(visible)}"
        )
    ws = visible[0]

    # Layout sanity: row-13 header must look like the ATR table.
    c13 = (_cell(ws, "C13") or "").lower()
    h13 = (_cell(ws, "H13") or "").lower()
    if "part number" not in c13 or "weight" not in h13:
        raise ValueError("unrecognized ATR layout (row-13 header mismatch)")

    header = ParsedHeader(
        customer=_cell(ws, "D1"),
        ac_programme=_cell(ws, "D2"),
        work_package=_cell(ws, "D3"),
        purchaser_spec=_cell(ws, "D4"),
        atp=_cell(ws, "D5"),
        supplier_spec=_cell(ws, "D6"),
        reference_no=_cell(ws, "D7"),
        supplier=_cell(ws, "D8"),
        customer_spec=_cell(ws, "G8"),
        nscm_code=_cell(ws, "G4"),
        ata_chapter=_cell(ws, "G3"),
        weighing_equipment=_cell(ws, "F12"),
    )

    parts: list[ParsedPart] = []
    warnings: list[str] = []
    category: str | None = None
    order = 0
    for r in range(15, ws.max_row + 1):
        a = _cell(ws, f"A{r}")
        c = _cell(ws, f"C{r}")
        f = _cell(ws, f"F{r}")
        if f and "total" in f.lower():
            break  # totals block — stop scanning parts
        if c and c.upper().startswith("VR"):
            weight = _to_decimal(ws[f"H{r}"].value)
            if ws[f"H{r}"].value not in (None, "") and weight is None:
                warnings.append(f"row {r}: unparseable weight {ws[f'H{r}'].value!r}")
            order += 1
            parts.append(ParsedPart(
                row_order=order,
                category=category,
                supplier_article_code=_cell(ws, f"B{r}"),
                part_number=c,
                part_number_norm=norm_partno(c),
                part_name=_cell(ws, f"D{r}"),
                serial_number=_cell(ws, f"E{r}"),
                drawing_number_issue=f,
                qty=_to_int(ws[f"G{r}"].value),
                default_weight_kg=weight,
            ))
        elif a and not c:
            if a.lower().startswith("if applicable"):
                continue
            category = a  # section header

    if not parts:
        warnings.append("no part rows found")
    return ParsedWorkbook(source_filename=source_filename, header=header,
                          parts=parts, warnings=warnings)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `docker compose exec -T api pytest backend/tests/test_atr_reference_import.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/atr_reference_import.py backend/tests/_atr_fixtures.py backend/tests/test_atr_reference_import.py
git commit -m "feat(atr): xlsx reference workbook parser"
```

---

## Task 3: Pydantic schemas

**Files:**
- Create: `backend/app/schemas/atr.py`
- Modify: `backend/app/schemas/__init__.py`
- Test: `backend/tests/test_atr_schemas.py`

**Interfaces:**
- Produces (importable from `app.schemas`): `AtrPartRead`, `AtrPartCreate`, `AtrPartUpdate`, `AtrTemplateRead`, `AtrTemplateUpdate`, `AtrImportPartPreview`, `AtrImportPreview`, `AtrImportResult`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_schemas.py
from decimal import Decimal

from app.schemas import AtrPartCreate, AtrImportPreview


def test_part_create_defaults():
    p = AtrPartCreate(part_number="VR11S 1010 016 000")
    assert p.qty == 1
    assert p.default_weight_kg is None


def test_import_preview_shape():
    pv = AtrImportPreview(
        source_filename="x.xlsx", header={}, parts=[],
        new_count=0, updated_count=0, unchanged_count=0, warnings=[],
    )
    assert pv.new_count == 0
    # Decimal accepted where present
    AtrPartCreate(part_number="X", default_weight_kg=Decimal("1.2"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest backend/tests/test_atr_schemas.py -v`
Expected: FAIL with `ImportError: cannot import name 'AtrPartCreate'`.

- [ ] **Step 3: Write the schemas**

```python
# backend/app/schemas/atr.py
"""Pydantic v2 DTOs for the ATR module (Phase A)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class AtrPartRead(BaseModel):
    id: int
    part_number: str
    part_number_norm: str
    supplier_article_code: str | None
    part_name: str | None
    drawing_number_issue: str | None
    default_weight_kg: Decimal | None
    qty: int
    category: str | None
    po_pos: str | None
    source_filename: str
    imported_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class AtrPartCreate(BaseModel):
    part_number: str = Field(..., max_length=60)
    supplier_article_code: str | None = Field(default=None, max_length=40)
    part_name: str | None = Field(default=None, max_length=200)
    drawing_number_issue: str | None = Field(default=None, max_length=60)
    default_weight_kg: Decimal | None = None
    qty: int = 1
    category: str | None = Field(default=None, max_length=40)
    po_pos: str | None = Field(default=None, max_length=20)


class AtrPartUpdate(BaseModel):
    part_number: str | None = Field(default=None, max_length=60)
    supplier_article_code: str | None = Field(default=None, max_length=40)
    part_name: str | None = Field(default=None, max_length=200)
    drawing_number_issue: str | None = Field(default=None, max_length=60)
    default_weight_kg: Decimal | None = None
    qty: int | None = None
    category: str | None = Field(default=None, max_length=40)
    po_pos: str | None = Field(default=None, max_length=20)


class AtrTemplateRead(BaseModel):
    id: int
    customer: str | None
    ac_programme: str | None
    work_package: str | None
    purchaser_spec: str | None
    atp: str | None
    supplier_spec: str | None
    reference_no: str | None
    supplier: str | None
    customer_spec: str | None
    nscm_code: str | None
    ata_chapter: str | None
    weighing_equipment: str | None
    qa_signer_default: str | None
    structure_filename: str | None
    has_structure: bool
    updated_at: datetime
    model_config = {"from_attributes": True}


class AtrTemplateUpdate(BaseModel):
    customer: str | None = Field(default=None, max_length=200)
    ac_programme: str | None = Field(default=None, max_length=100)
    work_package: str | None = None
    purchaser_spec: str | None = Field(default=None, max_length=200)
    atp: str | None = Field(default=None, max_length=200)
    supplier_spec: str | None = Field(default=None, max_length=200)
    reference_no: str | None = Field(default=None, max_length=200)
    supplier: str | None = Field(default=None, max_length=200)
    customer_spec: str | None = Field(default=None, max_length=100)
    nscm_code: str | None = Field(default=None, max_length=40)
    ata_chapter: str | None = Field(default=None, max_length=20)
    weighing_equipment: str | None = Field(default=None, max_length=100)
    qa_signer_default: str | None = Field(default=None, max_length=100)


class AtrImportPartPreview(BaseModel):
    part_number: str
    part_number_norm: str
    supplier_article_code: str | None
    part_name: str | None
    drawing_number_issue: str | None
    default_weight_kg: Decimal | None
    qty: int
    category: str | None
    status: Literal["new", "updated", "unchanged"]


class AtrImportPreview(BaseModel):
    source_filename: str
    header: dict
    parts: list[AtrImportPartPreview]
    new_count: int
    updated_count: int
    unchanged_count: int
    warnings: list[str]


class AtrImportResult(BaseModel):
    source_filename: str
    created: int
    updated: int
    template_updated: bool
    structure_set: bool
    warnings: list[str]
```

Then in `backend/app/schemas/__init__.py` add:

```python
from app.schemas.atr import (  # noqa: F401
    AtrImportPartPreview,
    AtrImportPreview,
    AtrImportResult,
    AtrPartCreate,
    AtrPartRead,
    AtrPartUpdate,
    AtrTemplateRead,
    AtrTemplateUpdate,
)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose exec -T api pytest backend/tests/test_atr_schemas.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/atr.py backend/app/schemas/__init__.py backend/tests/test_atr_schemas.py
git commit -m "feat(atr): pydantic schemas"
```

---

## Task 4: Router — parts CRUD + registration

**Files:**
- Create: `backend/app/routers/atr.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_atr_router.py`

**Interfaces:**
- Consumes: `AtrPart` model; `AtrPartRead/Create/Update` schemas; `get_async_db_session`, `get_current_user`, `require_admin`; `norm_partno`.
- Produces: `router` mounted at `/api/atr` with `GET/POST /parts`, `GET/PATCH/DELETE /parts/{id}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_router.py
# pytest.ini sets asyncio_mode = auto, so plain `async def test_*` works.
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


async def test_create_list_patch_delete_part(client):
    # create
    r = await client.post("/api/atr/parts", headers=_auth(), json={
        "part_number": "VR11S 1010 016 000",
        "part_name": "CARPET EMERGENCY EXIT HATCH",
        "drawing_number_issue": "VR11S 1010-10/D",
        "default_weight_kg": "0.413",
        "category": "CARPET",
    })
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["part_number_norm"] == "111010016000"

    # duplicate norm → 409
    r = await client.post("/api/atr/parts", headers=_auth(), json={
        "part_number": "VR11S1010016000",
    })
    assert r.status_code == 409

    # list + search
    r = await client.get("/api/atr/parts?search=EXIT", headers=_auth())
    assert r.status_code == 200
    assert any(p["id"] == pid for p in r.json())

    # patch
    r = await client.patch(f"/api/atr/parts/{pid}", headers=_auth(),
                           json={"po_pos": "050"})
    assert r.status_code == 200
    assert r.json()["po_pos"] == "050"

    # delete
    r = await client.delete(f"/api/atr/parts/{pid}", headers=_auth())
    assert r.status_code == 204
    r = await client.get(f"/api/atr/parts/{pid}", headers=_auth())
    assert r.status_code == 404
```

> Note: `tests/_auth.py` already exists (used by `conftest.py`); `mint`/`ADMIN_UUID` are its public helpers.

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest backend/tests/test_atr_router.py -v`
Expected: FAIL (404s — router not mounted).

- [ ] **Step 3: Write the router**

```python
# backend/app/routers/atr.py
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
```

Then in `backend/app/main.py`: add `from app.routers.atr import router as atr_router` with the other router imports, and `app.include_router(atr_router)` with the other includes.

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose exec -T api pytest backend/tests/test_atr_router.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/atr.py backend/app/main.py backend/tests/test_atr_router.py
git commit -m "feat(atr): parts catalog CRUD router"
```

---

## Task 5: Router — import preview + commit

**Files:**
- Modify: `backend/app/routers/atr.py`
- Test: `backend/tests/test_atr_merge.py`

**Interfaces:**
- Consumes: `parse_workbook`, `ParsedWorkbook`; `AtrPart`, `AtrTemplate`; `AtrImportPreview`, `AtrImportPartPreview`, `AtrImportResult`.
- Produces: `POST /api/atr/import/preview`, `POST /api/atr/import/commit`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_merge.py
from tests._atr_fixtures import build_atr_workbook_bytes
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


def _file(name="demo.xlsx", parts=None):
    data = build_atr_workbook_bytes(parts=parts)
    return {"files": (name, data,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}


async def test_preview_then_commit_then_merge(client):
    # preview: both parts are new
    r = await client.post("/api/atr/import/preview", headers=_auth(), files=_file())
    assert r.status_code == 200, r.text
    body = r.json()[0]
    assert body["new_count"] == 2 and body["updated_count"] == 0

    # commit: creates 2
    r = await client.post("/api/atr/import/commit", headers=_auth(),
                          files=_file(), data={"update_template": "true"})
    assert r.status_code == 200, r.text
    assert r.json()[0]["created"] == 2

    # re-import the SAME part number with a different weight → updated, not new
    changed = [("6060", "VR11S 1010 016 000", "CARPET EMERGENCY EXIT HATCH",
                "N/A", "VR11S 1010-10/D", 1, "0.999")]
    r = await client.post("/api/atr/import/preview", headers=_auth(),
                          files=_file(name="v2.xlsx", parts=changed))
    pv = r.json()[0]
    assert pv["updated_count"] == 1 and pv["new_count"] == 0
    assert pv["parts"][0]["status"] == "updated"

    r = await client.post("/api/atr/import/commit", headers=_auth(),
                          files=_file(name="v2.xlsx", parts=changed))
    assert r.json()[0]["updated"] == 1

    # catalog still has one row for that norm, with the new weight + source
    r = await client.get("/api/atr/parts?search=016%20000", headers=_auth())
    rows = [p for p in r.json() if p["part_number_norm"] == "111010016000"]
    assert len(rows) == 1
    assert rows[0]["default_weight_kg"] == "0.999"
    assert rows[0]["source_filename"] == "v2.xlsx"

    # template defaults were seeded from the import
    r = await client.get("/api/atr/template", headers=_auth())
    assert r.json()["nscm_code"] == "C9312"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest backend/tests/test_atr_merge.py -v`
Expected: FAIL (404 — import endpoints missing).

- [ ] **Step 3: Add the import endpoints**

Append to `backend/app/routers/atr.py` (add imports `from fastapi import File, Form, UploadFile`; `from app.models import AtrTemplate`; `from app.schemas import AtrImportPreview, AtrImportPartPreview, AtrImportResult`; `from app.services.atr_reference_import import parse_workbook, ParsedWorkbook`):

```python
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


def _value_fields(part) -> tuple:
    """The fields an import overwrites — used to classify new/updated/unchanged."""
    return (
        part.supplier_article_code, part.part_name, part.drawing_number_issue,
        part.default_weight_kg, part.qty, part.category,
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

        tmpl = (await db.execute(select(AtrTemplate).where(AtrTemplate.id == 1))).scalar_one()
        template_updated = False
        if update_template:
            for k, v in _header_dict(pw).items():
                setattr(tmpl, k, v)
            tmpl.updated_at = now
            template_updated = True
        structure_set = False
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
```

> The `GET /api/atr/template` endpoint the test calls is added in Task 6; this task's test asserts template defaults via that endpoint, so run Task 5 and Task 6 together if executing strictly sequentially, OR temporarily assert the template via a direct DB read. The recommended order is: implement Task 6 immediately after Task 5 before running the merge test's final assertion.

- [ ] **Step 4: Run the test to verify it passes** (after Task 6's `GET /template` exists)

Run: `docker compose exec -T api pytest backend/tests/test_atr_merge.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/atr.py backend/tests/test_atr_merge.py
git commit -m "feat(atr): xlsx import preview + commit with upsert merge"
```

---

## Task 6: Router — template singleton (get / patch / structure)

**Files:**
- Modify: `backend/app/routers/atr.py`
- Test: `backend/tests/test_atr_template.py`

**Interfaces:**
- Consumes: `AtrTemplate`; `AtrTemplateRead`, `AtrTemplateUpdate`.
- Produces: `GET /api/atr/template`, `PATCH /api/atr/template`, `POST /api/atr/template/structure`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_template.py
from tests._atr_fixtures import build_atr_workbook_bytes
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


async def test_template_get_patch_structure(client):
    r = await client.get("/api/atr/template", headers=_auth())
    assert r.status_code == 200
    assert r.json()["id"] == 1
    assert r.json()["has_structure"] is False

    r = await client.patch("/api/atr/template", headers=_auth(),
                           json={"customer_spec": "C9312", "qa_signer_default": "Cordula Kesseler i.A."})
    assert r.status_code == 200
    assert r.json()["customer_spec"] == "C9312"

    files = {"file": ("t.xlsx", build_atr_workbook_bytes(),
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = await client.post("/api/atr/template/structure", headers=_auth(), files=files)
    assert r.status_code == 200
    assert r.json()["has_structure"] is True
    assert r.json()["structure_filename"] == "t.xlsx"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest backend/tests/test_atr_template.py -v`
Expected: FAIL (404).

- [ ] **Step 3: Add the template endpoints**

Append to `backend/app/routers/atr.py` (ensure `AtrTemplateRead`, `AtrTemplateUpdate` imported from `app.schemas`):

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose exec -T api pytest backend/tests/test_atr_template.py backend/tests/test_atr_merge.py -v`
Expected: PASS (both files).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/atr.py backend/tests/test_atr_template.py
git commit -m "feat(atr): template singleton get/patch/structure endpoints"
```

---

## Task 7: Admin-gate audit test

**Files:**
- Test: `backend/tests/test_atr_admin_gate.py`

**Interfaces:**
- Consumes: the mounted `/api/atr/*` routes; `require_admin`.

- [ ] **Step 1: Write the test**

```python
# backend/tests/test_atr_admin_gate.py
"""Every /api/atr/* route must carry require_admin (mirrors test_sensors_admin_gate)."""
from fastapi.routing import APIRoute

from app.main import app
from app.security.directus_auth import require_admin
from tests._auth import VIEWER_UUID, mint


def _walk_deps(deps):
    out = []
    for d in deps:
        out.append(d.call)
        out.extend(_walk_deps(d.dependencies))
    return out


def test_atr_routes_registered():
    routes = [r for r in app.routes
              if isinstance(r, APIRoute) and r.path.startswith("/api/atr")]
    # parts: list, get, create, patch, delete; import: preview, commit; template: get, patch, structure
    assert len(routes) >= 10, [(r.path, sorted(r.methods)) for r in routes]


def test_every_atr_route_has_require_admin():
    routes = [r for r in app.routes
              if isinstance(r, APIRoute) and r.path.startswith("/api/atr")]
    for route in routes:
        calls = _walk_deps(route.dependant.dependencies)
        assert require_admin in calls, f"{sorted(route.methods)} {route.path} missing require_admin"


async def test_viewer_gets_403(client):
    r = await client.get("/api/atr/parts",
                         headers={"Authorization": f"Bearer {mint(VIEWER_UUID)}"})
    assert r.status_code == 403


async def test_no_token_gets_401(client):
    r = await client.get("/api/atr/parts")
    assert r.status_code == 401
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `docker compose exec -T api pytest backend/tests/test_atr_admin_gate.py backend/tests/test_admin_gate_audit.py -v`
Expected: PASS (the module-wide audit guard also stays green).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_atr_admin_gate.py
git commit -m "test(atr): admin-gate audit for /api/atr/*"
```

---

## Task 8: Frontend API client + i18n keys

**Files:**
- Create: `frontend/src/lib/atrApi.ts`
- Modify: `frontend/src/locales/en.json`, `frontend/src/locales/de.json`

**Interfaces:**
- Produces: TS types `AtrPart`, `AtrTemplate`, `AtrImportPreview`, `AtrImportPartPreview`, `AtrImportResult` and fetchers `fetchAtrParts`, `createAtrPart`, `updateAtrPart`, `deleteAtrPart`, `fetchAtrTemplate`, `updateAtrTemplate`, `atrImportPreview`, `atrImportCommit`, `setAtrStructure`.

- [ ] **Step 1: Write the API module**

```typescript
// frontend/src/lib/atrApi.ts
import { apiClient } from "./apiClient";

export interface AtrPart {
  id: number;
  part_number: string;
  part_number_norm: string;
  supplier_article_code: string | null;
  part_name: string | null;
  drawing_number_issue: string | null;
  default_weight_kg: string | null; // Decimal as string
  qty: number;
  category: string | null;
  po_pos: string | null;
  source_filename: string;
  imported_at: string;
  updated_at: string;
}

export interface AtrPartUpdate {
  part_number?: string;
  supplier_article_code?: string | null;
  part_name?: string | null;
  drawing_number_issue?: string | null;
  default_weight_kg?: string | null;
  qty?: number;
  category?: string | null;
  po_pos?: string | null;
}

export interface AtrTemplate {
  id: number;
  customer: string | null;
  ac_programme: string | null;
  work_package: string | null;
  purchaser_spec: string | null;
  atp: string | null;
  supplier_spec: string | null;
  reference_no: string | null;
  supplier: string | null;
  customer_spec: string | null;
  nscm_code: string | null;
  ata_chapter: string | null;
  weighing_equipment: string | null;
  qa_signer_default: string | null;
  structure_filename: string | null;
  has_structure: boolean;
  updated_at: string;
}

export interface AtrImportPartPreview {
  part_number: string;
  part_number_norm: string;
  supplier_article_code: string | null;
  part_name: string | null;
  drawing_number_issue: string | null;
  default_weight_kg: string | null;
  qty: number;
  category: string | null;
  status: "new" | "updated" | "unchanged";
}

export interface AtrImportPreview {
  source_filename: string;
  header: Record<string, string | null>;
  parts: AtrImportPartPreview[];
  new_count: number;
  updated_count: number;
  unchanged_count: number;
  warnings: string[];
}

export interface AtrImportResult {
  source_filename: string;
  created: number;
  updated: number;
  template_updated: boolean;
  structure_set: boolean;
  warnings: string[];
}

export async function fetchAtrParts(search?: string): Promise<AtrPart[]> {
  const qs = search ? `?search=${encodeURIComponent(search)}` : "";
  return apiClient<AtrPart[]>(`/api/atr/parts${qs}`);
}

export async function createAtrPart(body: { part_number: string }): Promise<AtrPart> {
  return apiClient<AtrPart>("/api/atr/parts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function updateAtrPart(id: number, body: AtrPartUpdate): Promise<AtrPart> {
  return apiClient<AtrPart>(`/api/atr/parts/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function deleteAtrPart(id: number): Promise<void> {
  await apiClient<void>(`/api/atr/parts/${id}`, { method: "DELETE" });
}

export async function fetchAtrTemplate(): Promise<AtrTemplate> {
  return apiClient<AtrTemplate>("/api/atr/template");
}

export async function updateAtrTemplate(body: Partial<AtrTemplate>): Promise<AtrTemplate> {
  return apiClient<AtrTemplate>("/api/atr/template", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function atrImportPreview(files: File[]): Promise<AtrImportPreview[]> {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  return apiClient<AtrImportPreview[]>("/api/atr/import/preview", {
    method: "POST",
    body: fd,
  });
}

export async function atrImportCommit(
  files: File[],
  opts?: { update_template?: boolean; set_structure?: boolean },
): Promise<AtrImportResult[]> {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  fd.append("update_template", String(opts?.update_template ?? false));
  fd.append("set_structure", String(opts?.set_structure ?? false));
  return apiClient<AtrImportResult[]>("/api/atr/import/commit", {
    method: "POST",
    body: fd,
  });
}

export async function setAtrStructure(file: File): Promise<AtrTemplate> {
  const fd = new FormData();
  fd.append("file", file);
  return apiClient<AtrTemplate>("/api/atr/template/structure", {
    method: "POST",
    body: fd,
  });
}
```

- [ ] **Step 2: Add i18n keys**

In `frontend/src/locales/en.json` add an `"atr"` object (place alongside the existing top-level keys):

```json
"atr": {
  "title": "ATR Reference",
  "tile": "ATR Reference",
  "nav": { "parts": "Parts catalog", "import": "Import", "template": "Template" },
  "parts": {
    "heading": "Parts catalog",
    "search": "Search part number, name, article…",
    "col": { "part_number": "Part number", "name": "Part name", "category": "Category", "drawing": "Drawing / Issue", "weight": "Weight [kg]", "po_pos": "PO Pos", "source": "Source file" },
    "empty": "No parts yet — import a reference workbook.",
    "save": "Save", "edit": "Edit", "delete": "Delete"
  },
  "import": {
    "heading": "Import reference workbook",
    "choose": "Choose .xlsx file(s)",
    "preview": "Preview",
    "commit": "Import",
    "update_template": "Also update template header defaults",
    "set_structure": "Use this workbook as the structural template",
    "new": "New", "updated": "Updated", "unchanged": "Unchanged",
    "warnings": "Warnings"
  },
  "template": {
    "heading": "Structural template & header defaults",
    "structure": "Structural workbook",
    "no_structure": "No structural workbook set",
    "upload_structure": "Upload structural workbook",
    "save": "Save defaults"
  }
}
```

In `frontend/src/locales/de.json` add the German mirror:

```json
"atr": {
  "title": "ATR Referenz",
  "tile": "ATR Referenz",
  "nav": { "parts": "Teilekatalog", "import": "Import", "template": "Vorlage" },
  "parts": {
    "heading": "Teilekatalog",
    "search": "Teilenummer, Bezeichnung, Artikel suchen…",
    "col": { "part_number": "Teilenummer", "name": "Bezeichnung", "category": "Kategorie", "drawing": "Zeichnung / Index", "weight": "Gewicht [kg]", "po_pos": "PO Pos", "source": "Quelldatei" },
    "empty": "Noch keine Teile — bitte eine Referenzdatei importieren.",
    "save": "Speichern", "edit": "Bearbeiten", "delete": "Löschen"
  },
  "import": {
    "heading": "Referenzdatei importieren",
    "choose": ".xlsx-Datei(en) wählen",
    "preview": "Vorschau",
    "commit": "Importieren",
    "update_template": "Auch Vorlagen-Kopfdaten aktualisieren",
    "set_structure": "Diese Datei als Struktur-Vorlage verwenden",
    "new": "Neu", "updated": "Aktualisiert", "unchanged": "Unverändert",
    "warnings": "Warnungen"
  },
  "template": {
    "heading": "Struktur-Vorlage & Kopfdaten",
    "structure": "Struktur-Arbeitsmappe",
    "no_structure": "Keine Struktur-Vorlage hinterlegt",
    "upload_structure": "Struktur-Arbeitsmappe hochladen",
    "save": "Kopfdaten speichern"
  }
}
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors from `atrApi.ts`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/atrApi.ts frontend/src/locales/en.json frontend/src/locales/de.json
git commit -m "feat(atr): frontend api client + i18n keys"
```

---

## Task 9: Parts catalog page + route + launcher tile

**Files:**
- Create: `frontend/src/pages/AtrPartsPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/LauncherPage.tsx`
- Test: `frontend/src/pages/__tests__/AtrPartsPage.test.tsx`

**Interfaces:**
- Consumes: `fetchAtrParts`, `updateAtrPart`, `deleteAtrPart` from `atrApi`.

- [ ] **Step 1: Write the page**

```tsx
// frontend/src/pages/AtrPartsPage.tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  fetchAtrParts, updateAtrPart, deleteAtrPart, type AtrPart,
} from "@/lib/atrApi";

export function AtrPartsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const { data: parts, isLoading } = useQuery({
    queryKey: ["atr", "parts", search],
    queryFn: () => fetchAtrParts(search || undefined),
  });
  const [editId, setEditId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Partial<AtrPart>>({});

  const save = useMutation({
    mutationFn: (id: number) => updateAtrPart(id, {
      po_pos: draft.po_pos ?? null,
      default_weight_kg: draft.default_weight_kg ?? null,
      drawing_number_issue: draft.drawing_number_issue ?? null,
      part_name: draft.part_name ?? null,
    }),
    onSuccess: () => {
      toast.success(t("atr.parts.save"));
      setEditId(null);
      qc.invalidateQueries({ queryKey: ["atr", "parts"] });
    },
    onError: (e: unknown) => toast.error(String(e)),
  });
  const remove = useMutation({
    mutationFn: (id: number) => deleteAtrPart(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["atr", "parts"] }),
  });

  return (
    <div className="max-w-6xl mx-auto px-6 py-6">
      <h1 className="text-xl font-semibold mb-4">{t("atr.parts.heading")}</h1>
      <input
        className="border rounded px-3 py-2 mb-4 w-full max-w-md"
        placeholder={t("atr.parts.search")}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        aria-label={t("atr.parts.search")}
      />
      {isLoading ? (
        <p>…</p>
      ) : !parts || parts.length === 0 ? (
        <p className="text-muted-foreground">{t("atr.parts.empty")}</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left border-b">
              <th className="py-2">{t("atr.parts.col.part_number")}</th>
              <th>{t("atr.parts.col.name")}</th>
              <th>{t("atr.parts.col.category")}</th>
              <th>{t("atr.parts.col.drawing")}</th>
              <th>{t("atr.parts.col.weight")}</th>
              <th>{t("atr.parts.col.po_pos")}</th>
              <th>{t("atr.parts.col.source")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {parts.map((p) => {
              const editing = editId === p.id;
              return (
                <tr key={p.id} className="border-b" data-testid={`atr-part-${p.id}`}>
                  <td className="py-1 font-mono">{p.part_number}</td>
                  <td>{editing ? (
                    <input className="border rounded px-1" defaultValue={p.part_name ?? ""}
                      onChange={(e) => setDraft((d) => ({ ...d, part_name: e.target.value }))} />
                  ) : p.part_name}</td>
                  <td>{p.category}</td>
                  <td>{editing ? (
                    <input className="border rounded px-1" defaultValue={p.drawing_number_issue ?? ""}
                      onChange={(e) => setDraft((d) => ({ ...d, drawing_number_issue: e.target.value }))} />
                  ) : p.drawing_number_issue}</td>
                  <td>{editing ? (
                    <input className="border rounded px-1 w-20" defaultValue={p.default_weight_kg ?? ""}
                      onChange={(e) => setDraft((d) => ({ ...d, default_weight_kg: e.target.value }))} />
                  ) : p.default_weight_kg}</td>
                  <td>{editing ? (
                    <input className="border rounded px-1 w-16" defaultValue={p.po_pos ?? ""}
                      onChange={(e) => setDraft((d) => ({ ...d, po_pos: e.target.value }))} />
                  ) : p.po_pos}</td>
                  <td className="text-xs text-muted-foreground">{p.source_filename}</td>
                  <td className="whitespace-nowrap">
                    {editing ? (
                      <button className="text-blue-600 mr-2" onClick={() => save.mutate(p.id)}>
                        {t("atr.parts.save")}
                      </button>
                    ) : (
                      <button className="text-blue-600 mr-2"
                        onClick={() => { setEditId(p.id); setDraft(p); }}>
                        {t("atr.parts.edit")}
                      </button>
                    )}
                    <button className="text-red-600" onClick={() => remove.mutate(p.id)}>
                      {t("atr.parts.delete")}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire the route + launcher tile**

In `frontend/src/App.tsx`: import `import { AtrPartsPage } from "./pages/AtrPartsPage";` and add routes inside the `<Switch>` (before `/settings` routes), all admin-gated:

```tsx
<Route path="/atr/import"><AdminOnly><AtrImportPage /></AdminOnly></Route>
<Route path="/atr/template"><AdminOnly><AtrTemplatePage /></AdminOnly></Route>
<Route path="/atr"><AdminOnly><AtrPartsPage /></AdminOnly></Route>
```

Add the imports for `AtrImportPage` and `AtrTemplatePage` too (created in Tasks 10–11):

```tsx
import { AtrImportPage } from "./pages/AtrImportPage";
import { AtrTemplatePage } from "./pages/AtrTemplatePage";
```

In `frontend/src/pages/LauncherPage.tsx`: add `FileSpreadsheet` to the lucide import, and an admin tile after the signage tile:

```tsx
<AdminOnly>
  <div className="flex flex-col items-center gap-2">
    <button
      type="button"
      onClick={() => setLocation("/atr")}
      aria-label={t("atr.tile")}
      className="w-[120px] h-[120px] rounded-2xl
                 bg-gradient-to-br from-slate-500 to-gray-700
                 shadow-md hover:shadow-xl hover:scale-[1.03]
                 flex items-center justify-center p-4
                 cursor-pointer transition-all
                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <FileSpreadsheet className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
    </button>
    <span className="text-xs text-muted-foreground text-center">{t("atr.tile")}</span>
  </div>
</AdminOnly>
```

- [ ] **Step 3: Write the render test**

```tsx
// frontend/src/pages/__tests__/AtrPartsPage.test.tsx
import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import { describe, it, expect, vi, beforeEach } from "vitest";
import i18n from "@/i18n";
import { AtrPartsPage } from "../AtrPartsPage";
import * as atrApi from "@/lib/atrApi";

vi.mock("@/lib/atrApi");

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>{ui}</I18nextProvider>
    </QueryClientProvider>
  );
}

describe("AtrPartsPage", () => {
  beforeEach(() => vi.resetAllMocks());

  it("renders catalog rows with source file", async () => {
    vi.mocked(atrApi.fetchAtrParts).mockResolvedValue([{
      id: 1, part_number: "VR11S 1010 016 000", part_number_norm: "111010016000",
      supplier_article_code: "6060", part_name: "CARPET EMERGENCY EXIT HATCH",
      drawing_number_issue: "VR11S 1010-10/D", default_weight_kg: "0.413", qty: 1,
      category: "CARPET", po_pos: null, source_filename: "demo.xlsx",
      imported_at: "2026-06-25T00:00:00Z", updated_at: "2026-06-25T00:00:00Z",
    }]);
    render(wrap(<AtrPartsPage />));
    await waitFor(() => expect(screen.getByTestId("atr-part-1")).toBeInTheDocument());
    expect(screen.getByText("demo.xlsx")).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/__tests__/AtrPartsPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/AtrPartsPage.tsx frontend/src/App.tsx frontend/src/pages/LauncherPage.tsx frontend/src/pages/__tests__/AtrPartsPage.test.tsx
git commit -m "feat(atr): parts catalog page, route, launcher tile"
```

---

## Task 10: Import page (preview → commit)

**Files:**
- Create: `frontend/src/pages/AtrImportPage.tsx`
- Test: `frontend/src/pages/__tests__/AtrImportPage.test.tsx`

**Interfaces:**
- Consumes: `atrImportPreview`, `atrImportCommit` from `atrApi`.

- [ ] **Step 1: Write the page**

```tsx
// frontend/src/pages/AtrImportPage.tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import {
  atrImportPreview, atrImportCommit, type AtrImportPreview,
} from "@/lib/atrApi";

export function AtrImportPage() {
  const { t } = useTranslation();
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<AtrImportPreview[] | null>(null);
  const [updateTemplate, setUpdateTemplate] = useState(false);
  const [setStructure, setSetStructure] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onPreview() {
    if (!files.length) return;
    setBusy(true);
    try {
      setPreviews(await atrImportPreview(files));
    } catch (e) { toast.error(String(e)); } finally { setBusy(false); }
  }

  async function onCommit() {
    setBusy(true);
    try {
      const res = await atrImportCommit(files, {
        update_template: updateTemplate, set_structure: setStructure,
      });
      const created = res.reduce((s, r) => s + r.created, 0);
      const updated = res.reduce((s, r) => s + r.updated, 0);
      toast.success(`${t("atr.import.commit")}: +${created} / ~${updated}`);
      setPreviews(null); setFiles([]);
    } catch (e) { toast.error(String(e)); } finally { setBusy(false); }
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-6">
      <h1 className="text-xl font-semibold mb-4">{t("atr.import.heading")}</h1>
      <input
        type="file" accept=".xlsx" multiple
        aria-label={t("atr.import.choose")}
        onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
      />
      <button className="ml-3 px-3 py-1 border rounded" disabled={!files.length || busy}
        onClick={onPreview}>{t("atr.import.preview")}</button>

      {previews && (
        <div className="mt-6 space-y-6">
          {previews.map((pv) => (
            <div key={pv.source_filename} className="border rounded p-4">
              <div className="font-medium mb-2">{pv.source_filename}</div>
              <div className="text-sm mb-2">
                <span className="text-green-600 mr-3">{t("atr.import.new")}: {pv.new_count}</span>
                <span className="text-amber-600 mr-3">{t("atr.import.updated")}: {pv.updated_count}</span>
                <span className="text-muted-foreground">{t("atr.import.unchanged")}: {pv.unchanged_count}</span>
              </div>
              {pv.warnings.length > 0 && (
                <ul className="text-xs text-red-600 mb-2" data-testid="atr-warnings">
                  {pv.warnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              )}
              <table className="w-full text-xs">
                <tbody>
                  {pv.parts.map((p) => (
                    <tr key={p.part_number_norm} data-status={p.status}>
                      <td className="font-mono pr-2">{p.part_number}</td>
                      <td className="pr-2">{p.part_name}</td>
                      <td className="pr-2">{p.default_weight_kg}</td>
                      <td className={p.status === "new" ? "text-green-600"
                        : p.status === "updated" ? "text-amber-600" : "text-muted-foreground"}>
                        {t(`atr.import.${p.status}`)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={updateTemplate}
              onChange={(e) => setUpdateTemplate(e.target.checked)} />
            {t("atr.import.update_template")}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={setStructure}
              onChange={(e) => setSetStructure(e.target.checked)} />
            {t("atr.import.set_structure")}
          </label>
          <button className="px-4 py-2 bg-blue-600 text-white rounded" disabled={busy}
            onClick={onCommit}>{t("atr.import.commit")}</button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Write the test**

```tsx
// frontend/src/pages/__tests__/AtrImportPage.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { describe, it, expect, vi, beforeEach } from "vitest";
import i18n from "@/i18n";
import { AtrImportPage } from "../AtrImportPage";
import * as atrApi from "@/lib/atrApi";

vi.mock("@/lib/atrApi");

describe("AtrImportPage", () => {
  beforeEach(() => vi.resetAllMocks());

  it("shows preview counts and warnings after choosing a file", async () => {
    vi.mocked(atrApi.atrImportPreview).mockResolvedValue([{
      source_filename: "demo.xlsx", header: {}, new_count: 2, updated_count: 0,
      unchanged_count: 0, warnings: ["row 9: unparseable weight"],
      parts: [{
        part_number: "VR11S 1010 016 000", part_number_norm: "111010016000",
        supplier_article_code: "6060", part_name: "CARPET", drawing_number_issue: "X",
        default_weight_kg: "0.413", qty: 1, category: "CARPET", status: "new",
      }],
    }]);
    render(
      <I18nextProvider i18n={i18n}>
        <AtrImportPage />
      </I18nextProvider>,
    );
    const input = screen.getByLabelText(/xlsx/i);
    const file = new File(["x"], "demo.xlsx",
      { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByText(/Preview|Vorschau/));
    await waitFor(() => expect(screen.getByText("demo.xlsx")).toBeInTheDocument());
    expect(screen.getByTestId("atr-warnings")).toHaveTextContent("unparseable weight");
  });
});
```

- [ ] **Step 3: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/__tests__/AtrImportPage.test.tsx`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AtrImportPage.tsx frontend/src/pages/__tests__/AtrImportPage.test.tsx
git commit -m "feat(atr): import preview/commit page"
```

---

## Task 11: Template page

**Files:**
- Create: `frontend/src/pages/AtrTemplatePage.tsx`
- Test: `frontend/src/pages/__tests__/AtrTemplatePage.test.tsx`

**Interfaces:**
- Consumes: `fetchAtrTemplate`, `updateAtrTemplate`, `setAtrStructure` from `atrApi`.

- [ ] **Step 1: Write the page**

```tsx
// frontend/src/pages/AtrTemplatePage.tsx
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  fetchAtrTemplate, updateAtrTemplate, setAtrStructure, type AtrTemplate,
} from "@/lib/atrApi";

const FIELDS: (keyof AtrTemplate)[] = [
  "customer", "ac_programme", "work_package", "purchaser_spec", "atp",
  "supplier_spec", "reference_no", "supplier", "customer_spec", "nscm_code",
  "ata_chapter", "weighing_equipment", "qa_signer_default",
];

export function AtrTemplatePage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["atr", "template"], queryFn: fetchAtrTemplate });
  const [draft, setDraft] = useState<Partial<AtrTemplate>>({});
  useEffect(() => { if (data) setDraft(data); }, [data]);

  async function save() {
    try {
      const body: Partial<AtrTemplate> = {};
      FIELDS.forEach((f) => { (body as Record<string, unknown>)[f] = draft[f] ?? null; });
      await updateAtrTemplate(body);
      toast.success(t("atr.template.save"));
      qc.invalidateQueries({ queryKey: ["atr", "template"] });
    } catch (e) { toast.error(String(e)); }
  }

  async function onStructure(file: File) {
    try {
      await setAtrStructure(file);
      toast.success(t("atr.template.structure"));
      qc.invalidateQueries({ queryKey: ["atr", "template"] });
    } catch (e) { toast.error(String(e)); }
  }

  if (!data) return <div className="p-6">…</div>;
  return (
    <div className="max-w-3xl mx-auto px-6 py-6">
      <h1 className="text-xl font-semibold mb-4">{t("atr.template.heading")}</h1>
      <div className="mb-6 text-sm">
        <span className="font-medium">{t("atr.template.structure")}: </span>
        {data.has_structure ? data.structure_filename : t("atr.template.no_structure")}
        <div className="mt-2">
          <input type="file" accept=".xlsx" aria-label={t("atr.template.upload_structure")}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onStructure(f); }} />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3">
        {FIELDS.map((f) => (
          <label key={f} className="flex flex-col text-sm">
            <span className="text-muted-foreground">{f}</span>
            <input className="border rounded px-2 py-1" value={(draft[f] as string) ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, [f]: e.target.value }))} />
          </label>
        ))}
      </div>
      <button className="mt-4 px-4 py-2 bg-blue-600 text-white rounded" onClick={save}>
        {t("atr.template.save")}
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Write the test**

```tsx
// frontend/src/pages/__tests__/AtrTemplatePage.test.tsx
import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import { describe, it, expect, vi, beforeEach } from "vitest";
import i18n from "@/i18n";
import { AtrTemplatePage } from "../AtrTemplatePage";
import * as atrApi from "@/lib/atrApi";

vi.mock("@/lib/atrApi");

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>{ui}</I18nextProvider>
    </QueryClientProvider>
  );
}

describe("AtrTemplatePage", () => {
  beforeEach(() => vi.resetAllMocks());

  it("renders header defaults from the template", async () => {
    vi.mocked(atrApi.fetchAtrTemplate).mockResolvedValue({
      id: 1, customer: "Diehl Aviation Laupheim GmbH", ac_programme: "A350 XWB",
      work_package: null, purchaser_spec: null, atp: null, supplier_spec: null,
      reference_no: null, supplier: null, customer_spec: "C9312", nscm_code: "C9312",
      ata_chapter: "25", weighing_equipment: "Plattenwaage PW015",
      qa_signer_default: "Cordula Kesseler i.A.", structure_filename: null,
      has_structure: false, updated_at: "2026-06-25T00:00:00Z",
    });
    render(wrap(<AtrTemplatePage />));
    await waitFor(() =>
      expect(screen.getByDisplayValue("Diehl Aviation Laupheim GmbH")).toBeInTheDocument());
    expect(screen.getByDisplayValue("Plattenwaage PW015")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/__tests__/AtrTemplatePage.test.tsx`
Expected: PASS.

- [ ] **Step 4: Final full-suite gate**

Run backend: `docker compose exec -T api pytest backend/tests/test_atr_*.py -v`
Run frontend: `cd frontend && npx vitest run src/pages/__tests__/Atr*.test.tsx && npx tsc --noEmit`
Expected: all PASS, no type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/AtrTemplatePage.tsx frontend/src/pages/__tests__/AtrTemplatePage.test.tsx
git commit -m "feat(atr): template defaults + structure page"
```

---

## Acceptance check (manual, after merge)

Not a unit test — run once against a dev environment with the real files:

1. Mount/copy the 12 reference workbooks somewhere reachable and import them via `/atr/import` (preview → commit, with "update template defaults" checked on one CCRC 6-Bett file and "set structural template" checked on it too).
2. Confirm the catalog holds one merged list of ≈120–150 distinct parts, each showing a source file.
3. Search `1010 048 000` → confirm CARPET BEDS FWD resolves to drawing `VR11S 1010-27/A` (the value from the example Lieferschein's parts), proving the Phase-B match key.
4. Delete the throwaway exploration scripts `scripts/atr_*.py`.

---

## Self-Review

- **Spec coverage:** `atr_part` global catalog with source provenance (Tasks 1,4,5) ✓; `atr_template` singleton + structure bytes (Tasks 1,6) ✓; importer with visible-sheet/row-13 rules, normalization, warnings (Task 2) ✓; preview→commit upsert/merge (Task 5) ✓; admin gate (Task 7) ✓; parts catalog + import + template UI with source column + German i18n (Tasks 8–11) ✓; merge/provenance test (Task 5) + acceptance check ✓.
- **Placeholder scan:** no TBD/TODO; all steps carry runnable code and commands.
- **Type consistency:** `part_number_norm` digits-only used identically in model/parser/router/TS; `parse_workbook` / `ParsedWorkbook` / `ParsedPart` names consistent across Tasks 2 and 5; `AtrImportResult`/`AtrImportPreview` fields match between schema (Task 3), router (Task 5), and TS (Task 8).
- **Cross-task ordering note:** Task 5's final assertion depends on Task 6's `GET /template`; execute Task 6 before running the Task-5 merge test (flagged inline).
