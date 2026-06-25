# ATR Phase B — Generate Documents from a Lieferschein Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse a Diehl Lieferschein PDF, enrich its positions from the ATR catalog, persist a reviewable draft delivery, and generate the ATR (.xlsx + PDF) + Containerbeschriftung (.docx) for download.

**Architecture:** New backend units in the existing `atr` module — a poppler-`pdftotext` Lieferschein parser, a catalog matcher, an openpyxl "template-as-frame" xlsx generator + LibreOffice xlsx→PDF, a python-docx label generator, and an admin-gated `/api/atr/deliveries` router persisting `atr_delivery` + `atr_delivery_item`. Three React pages (list + review) under `/atr/deliveries`. Manual trigger only (upload or pick from `ATR_INPUT_DIR`); scheduler/SMB/Output-write are Phase C.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async · Pydantic v2 · openpyxl 3.1.5 · python-docx 1.1.2 · poppler `pdftotext` · LibreOffice headless · React 19 · wouter · TanStack Query.

Reference spec: `docs/superpowers/specs/2026-06-25-atr-phase-b-generate-from-lieferschein.md`. Branch: `feat/atr-phase-b` (off Phase A `feat/atr-module`).

## Global Constraints

- **Admin-only.** Every `/api/atr/*` route (including `/api/atr/deliveries/*`) is gated at the router level: `dependencies=[Depends(get_current_user), Depends(require_admin)]` (mirror `routers/sensors.py`). Enforced by `tests/test_admin_gate_audit.py`.
- **Migration:** new `v1_64_atr_delivery`, `down_revision = "v1_63_atr_reference"` (re-verify head with `alembic heads`).
- **⚠ TEST DB SAFETY:** backend pytest DELETEs tables; with production `POSTGRES_*` it wipes the live `acm_kpi` DB. Run **only** against the disposable `acm_test` DB via `-e POSTGRES_DB=acm_test`. Never run pytest in a shell with the production `.env`. In-container test path is `tests/...` (workdir `/app`), e.g. `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_lieferschein.py -v`.
- **Subprocess must be async.** Use `asyncio.create_subprocess_exec` for `pdftotext` and `soffice` (sync `subprocess` blocks the event loop). Mirror `services/signage_pptx.py`: a module-level `asyncio.Semaphore(1)` + outer `asyncio.wait_for` timeout + per-invocation LibreOffice profile dir + `finally` cleanup.
- **Decimals on the wire are strings** (Pydantic). TS types use `string`, parse with `Number(...)`.
- **i18n keys are FLAT dot-strings** (project `i18n.ts` sets `keySeparator: false`). Add `atr.deliveries.*` keys to BOTH `en.json` and `de.json`; never nested objects.
- **part_number_norm = digits-only** of the part number (reuse `app.services.atr_reference_import.norm_partno`).
- Commit after every task. After image-affecting changes (Dockerfile/requirements) the implementer must rebuild the api image before running affected tests.

---

## File Structure

**Backend**
- Modify `backend/app/models/atr.py` — add `AtrDelivery`, `AtrDeliveryItem`.
- Modify `backend/app/models/__init__.py` — register.
- Create `backend/alembic/versions/v1_64_atr_delivery.py`.
- Create `backend/app/schemas/atr_delivery.py`; modify `backend/app/schemas/__init__.py`.
- Create `backend/app/services/atr_lieferschein.py` — PDF/text → parsed positions.
- Create `backend/app/services/atr_match.py` — positions → catalog enrichment.
- Create `backend/app/services/atr_generate_xlsx.py` — fill template + xlsx→PDF.
- Create `backend/app/services/atr_generate_docx.py` — label.
- Create `backend/app/routers/atr_delivery.py`; modify `backend/app/main.py`.
- Modify `backend/Dockerfile` (libreoffice-calc), `backend/requirements.txt` (python-docx), `docker-compose.yml` (`ATR_INPUT_DIR`).
- Tests under `backend/tests/` + fixtures under `backend/tests/fixtures/atr/`.

**Frontend**
- Modify `frontend/src/lib/atrApi.ts` — delivery types + fetchers.
- Modify `frontend/src/locales/en.json`, `de.json` — flat `atr.deliveries.*`.
- Create `frontend/src/pages/AtrDeliveriesPage.tsx`, `AtrDeliveryReviewPage.tsx`.
- Modify `frontend/src/App.tsx` — routes.
- Create tests under `frontend/src/pages/__tests__/`.

---

# Wave 1 — Ingest + match + persist

## Task 1: Delivery models + migration

**Files:**
- Modify: `backend/app/models/atr.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/v1_64_atr_delivery.py`
- Test: `backend/tests/test_atr_delivery_models.py`

**Interfaces:**
- Produces: `AtrDelivery` (table `atr_delivery`), `AtrDeliveryItem` (table `atr_delivery_item`), importable from `app.models`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_delivery_models.py
from app.models import AtrDelivery, AtrDeliveryItem
from app.database import Base


def test_delivery_tables_registered():
    assert "atr_delivery" in Base.metadata.tables
    assert "atr_delivery_item" in Base.metadata.tables


def test_delivery_item_fk_and_columns():
    cols = {c.name for c in AtrDeliveryItem.__table__.columns}
    assert {"delivery_id", "part_number_norm", "matched_part_id", "weight_kg",
            "po_pos", "match_status", "row_order"} <= cols
    fks = {list(fk.column.table.name for fk in c.foreign_keys)[0]
           for c in AtrDeliveryItem.__table__.columns if c.foreign_keys}
    assert "atr_delivery" in fks


def test_delivery_has_generated_byte_columns():
    cols = {c.name for c in AtrDelivery.__table__.columns}
    assert {"atr_xlsx", "atr_pdf", "label_docx", "status"} <= cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_delivery_models.py -v`
Expected: FAIL `ImportError: cannot import name 'AtrDelivery'`.

- [ ] **Step 3: Add the models**

Append to `backend/app/models/atr.py` (imports `Date`, `ForeignKey` may be needed — add to the existing sqlalchemy import line: `from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text`):

```python
class AtrDelivery(Base):
    """One processed Lieferschein (Phase B)."""
    __tablename__ = "atr_delivery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    lieferschein_nr: Mapped[str | None] = mapped_column(String(40), nullable=True)
    datum: Mapped[date | None] = mapped_column(Date, nullable=True)
    ba_auftrag: Mapped[str | None] = mapped_column(String(40), nullable=True)
    po_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ac_programme: Mapped[str | None] = mapped_column(String(40), nullable=True)
    compartment: Mapped[str | None] = mapped_column(String(8), nullable=True)
    msn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bed_config: Mapped[str | None] = mapped_column(String(8), nullable=True)
    set_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    atr_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    container_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    weighing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    testing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    qa_signer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    max_guaranteed_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    atr_xlsx: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    atr_pdf: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    label_docx: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    items: Mapped[list["AtrDeliveryItem"]] = relationship(
        "AtrDeliveryItem", back_populates="delivery",
        cascade="all, delete-orphan", order_by="AtrDeliveryItem.row_order",
    )


class AtrDeliveryItem(Base):
    """One Lieferschein position within a delivery."""
    __tablename__ = "atr_delivery_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    delivery_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("atr_delivery.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supplier_article_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    part_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    part_number_norm: Mapped[str | None] = mapped_column(String(40), nullable=True)
    matched_part_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("atr_part.id", ondelete="SET NULL"), nullable=True
    )
    part_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    drawing_number_issue: Mapped[str | None] = mapped_column(String(60), nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    po_pos: Mapped[str | None] = mapped_column(String(20), nullable=True)
    match_status: Mapped[str] = mapped_column(String(12), nullable=False, default="unmatched")
    row_order: Mapped[int] = mapped_column(Integer, nullable=False)

    delivery: Mapped["AtrDelivery"] = relationship("AtrDelivery", back_populates="items")
```

Add `from datetime import date` to the existing datetime import at the top of the file (`from datetime import date, datetime`). Then register in `backend/app/models/__init__.py`: extend the atr import to `from app.models.atr import AtrPart, AtrTemplate, AtrDelivery, AtrDeliveryItem  # noqa: F401` and add `"AtrDelivery", "AtrDeliveryItem",` to `__all__`.

- [ ] **Step 4: Write the migration**

```python
# backend/alembic/versions/v1_64_atr_delivery.py
"""v1.64: atr_delivery + atr_delivery_item (ATR Phase B)

Revision ID: v1_64_atr_delivery
Revises: v1_63_atr_reference
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "v1_64_atr_delivery"
down_revision = "v1_63_atr_reference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "atr_delivery",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_filename", sa.String(255), nullable=False),
        sa.Column("lieferschein_nr", sa.String(40), nullable=True),
        sa.Column("datum", sa.Date, nullable=True),
        sa.Column("ba_auftrag", sa.String(40), nullable=True),
        sa.Column("po_number", sa.String(60), nullable=True),
        sa.Column("ac_programme", sa.String(40), nullable=True),
        sa.Column("compartment", sa.String(8), nullable=True),
        sa.Column("msn", sa.String(20), nullable=True),
        sa.Column("bed_config", sa.String(8), nullable=True),
        sa.Column("set_title", sa.String(100), nullable=True),
        sa.Column("atr_number", sa.String(80), nullable=True),
        sa.Column("container_number", sa.String(40), nullable=True),
        sa.Column("weighing_date", sa.Date, nullable=True),
        sa.Column("testing_date", sa.Date, nullable=True),
        sa.Column("qa_signer", sa.String(100), nullable=True),
        sa.Column("max_guaranteed_weight_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("atr_xlsx", postgresql.BYTEA, nullable=True),
        sa.Column("atr_pdf", postgresql.BYTEA, nullable=True),
        sa.Column("label_docx", postgresql.BYTEA, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "atr_delivery_item",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("delivery_id", sa.Integer,
                  sa.ForeignKey("atr_delivery.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pos", sa.Integer, nullable=True),
        sa.Column("supplier_article_code", sa.String(40), nullable=True),
        sa.Column("part_number", sa.String(60), nullable=True),
        sa.Column("part_number_norm", sa.String(40), nullable=True),
        sa.Column("matched_part_id", sa.Integer,
                  sa.ForeignKey("atr_part.id", ondelete="SET NULL"), nullable=True),
        sa.Column("part_name", sa.String(200), nullable=True),
        sa.Column("drawing_number_issue", sa.String(60), nullable=True),
        sa.Column("category", sa.String(40), nullable=True),
        sa.Column("qty", sa.Integer, nullable=False, server_default="1"),
        sa.Column("weight_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("po_pos", sa.String(20), nullable=True),
        sa.Column("match_status", sa.String(12), nullable=False, server_default="unmatched"),
        sa.Column("row_order", sa.Integer, nullable=False),
    )
    op.create_index("ix_atr_delivery_item_delivery", "atr_delivery_item", ["delivery_id"])


def downgrade() -> None:
    op.drop_index("ix_atr_delivery_item_delivery", table_name="atr_delivery_item")
    op.drop_table("atr_delivery_item")
    op.drop_table("atr_delivery")
```

- [ ] **Step 5: Apply migration to the test DB**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api alembic upgrade head`
Expected: `Running upgrade v1_63_atr_reference -> v1_64_atr_delivery`.

- [ ] **Step 6: Run the test**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_delivery_models.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/atr.py backend/app/models/__init__.py backend/alembic/versions/v1_64_atr_delivery.py backend/tests/test_atr_delivery_models.py
git commit -m "feat(atr): atr_delivery + atr_delivery_item models and migration"
```

---

## Task 2: Lieferschein parser

**Files:**
- Create: `backend/app/services/atr_lieferschein.py`
- Create: `backend/tests/fixtures/atr/lieferschein_sample.txt`
- Test: `backend/tests/test_atr_lieferschein.py`

**Interfaces:**
- Produces: dataclasses `ParsedPosition`, `ParsedLieferschein`; `parse_lieferschein_text(text: str) -> ParsedLieferschein` (pure, tested); `async extract_pdf_text(pdf_bytes: bytes) -> str` (runs `pdftotext -layout`); `async parse_lieferschein(pdf_bytes: bytes) -> ParsedLieferschein`.

- [ ] **Step 1: Create the text fixture**

Create `backend/tests/fixtures/atr/lieferschein_sample.txt` with this content (a trimmed `pdftotext -layout` capture — 2 positions, enough to exercise every field + a malformed block):

```
                                                                       LIEFERSCHEIN
                                                                       Nr.                        20189798
                                                                       Datum                          08.06.2026
                                                                       Kunden Nr.                            10005
                                                                       Bearbeiter                            Ralf Zettler

Pos Artikel                       Menge ME
         Bezeichnung

1 6060                            1 STK
CARPET EMERG. EXIT HATCH
Bauteil-Index: D
Ihre Nr. VR11S1010016000
Auftrag Nr. 1024738 / 5
Bestelldaten 4501119979/A350/CCRC/MSN830/6-Bett

2 11395                           1 STK
CARPET BEDS FWD
TEPPICH BETTEN VORNE
Bauteilindex: A
Ihre Nr. VR11S1010048000
Auftrag Nr. 1024738 / 30
Bestelldaten 4501119979/A350/CCRC/MSN830/6-Bett
```

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_atr_lieferschein.py
from pathlib import Path

from app.services.atr_lieferschein import parse_lieferschein_text

FIX = Path(__file__).parent / "fixtures" / "atr" / "lieferschein_sample.txt"


def test_parse_header_and_positions():
    pl = parse_lieferschein_text(FIX.read_text(encoding="utf-8"))
    assert pl.lieferschein_nr == "20189798"
    assert pl.datum == "08.06.2026"
    assert len(pl.positions) == 2

    p1 = pl.positions[0]
    assert p1.pos == 1
    assert p1.supplier_article_code == "6060"
    assert p1.qty == 1
    assert p1.bezeichnung == "CARPET EMERG. EXIT HATCH"
    assert p1.index == "D"
    assert p1.part_number == "VR11S1010016000"
    assert p1.part_number_norm == "111010016000"
    assert p1.ba_auftrag == "1024738"
    assert p1.po_base == "4501119979"
    assert p1.ac_programme == "A350"
    assert p1.compartment == "CCRC"
    assert p1.msn == "830"
    assert p1.bed_config == "6"


def test_parse_missing_field_warns():
    text = "Nr. 999\n1 6060 1 STK\nCARPET X\nIhre Nr. VR11S1010016000\n"
    pl = parse_lieferschein_text(text)
    assert pl.positions and pl.positions[0].ba_auftrag is None
    assert any("auftrag" in w.lower() or "bestelldaten" in w.lower() for w in pl.warnings)


def test_zero_positions_warns():
    pl = parse_lieferschein_text("LIEFERSCHEIN\nNr. 1\n")
    assert pl.positions == []
    assert pl.warnings
```

- [ ] **Step 3: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_lieferschein.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 4: Write the parser**

```python
# backend/app/services/atr_lieferschein.py
"""Parse a Diehl Lieferschein PDF into header + positions (ATR Phase B).

Text extraction via poppler `pdftotext -layout` (async subprocess); the
text→struct parser is pure and unit-tested.
"""
from __future__ import annotations

import asyncio
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.services.atr_reference_import import norm_partno

_POS_RE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+([A-Za-z]+)\b")
_NR_RE = re.compile(r"\bNr\.\s+(\d+)")
_DATUM_RE = re.compile(r"\bDatum\s+(\d{2}\.\d{2}\.\d{4})")
_INDEX_RE = re.compile(r"Bauteil[- ]?[Ii]ndex:\s*([A-Za-z0-9]+)")
_IHRE_RE = re.compile(r"Ihre Nr\.\s*(\S+)")
_AUFTRAG_RE = re.compile(r"Auftrag Nr\.\s*(\d+)\s*/\s*(\d+)")
_BESTELL_RE = re.compile(r"Bestelldaten\s*(\S+)")


@dataclass
class ParsedPosition:
    pos: int | None = None
    supplier_article_code: str | None = None
    qty: int = 1
    bezeichnung: str | None = None
    index: str | None = None
    part_number: str | None = None
    part_number_norm: str | None = None
    ba_auftrag: str | None = None
    po_base: str | None = None
    ac_programme: str | None = None
    compartment: str | None = None
    msn: str | None = None
    bed_config: str | None = None


@dataclass
class ParsedLieferschein:
    lieferschein_nr: str | None = None
    datum: str | None = None
    positions: list[ParsedPosition] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _parse_bestelldaten(token: str, p: ParsedPosition) -> None:
    parts = token.split("/")
    if parts:
        p.po_base = parts[0] or None
    for seg in parts[1:]:
        s = seg.strip()
        if s in ("CCRC", "FCRC"):
            p.compartment = s
        elif s.upper().startswith("MSN"):
            p.msn = s[3:] or None
        elif re.fullmatch(r"\d-?Bett", s, re.IGNORECASE) or s.lower().endswith("bett"):
            m = re.match(r"(\d+)", s)
            p.bed_config = m.group(1) if m else None
        elif re.fullmatch(r"A\d{3}", s):
            p.ac_programme = s


def parse_lieferschein_text(text: str) -> ParsedLieferschein:
    pl = ParsedLieferschein()
    lines = text.splitlines()
    for line in lines:
        if pl.lieferschein_nr is None:
            m = _NR_RE.search(line)
            if m:
                pl.lieferschein_nr = m.group(1)
        if pl.datum is None:
            m = _DATUM_RE.search(line)
            if m:
                pl.datum = m.group(1)
        if pl.lieferschein_nr and pl.datum:
            break

    cur: ParsedPosition | None = None

    def _flush(p: ParsedPosition | None) -> None:
        if p is None:
            return
        for fname, label in (("ba_auftrag", "Auftrag"), ("part_number", "Ihre Nr"),
                             ("po_base", "Bestelldaten")):
            if getattr(p, fname) is None:
                pl.warnings.append(f"position {p.pos}: missing {label}")
        pl.positions.append(p)

    for line in lines:
        m = _POS_RE.match(line)
        if m:
            _flush(cur)
            cur = ParsedPosition(
                pos=int(m.group(1)), supplier_article_code=m.group(2),
                qty=int(m.group(3)),
            )
            continue
        if cur is None:
            continue
        mi = _IHRE_RE.search(line)
        if mi:
            cur.part_number = mi.group(1)
            cur.part_number_norm = norm_partno(mi.group(1))
            continue
        ma = _AUFTRAG_RE.search(line)
        if ma:
            cur.ba_auftrag = ma.group(1)
            continue
        mb = _BESTELL_RE.search(line)
        if mb:
            _parse_bestelldaten(mb.group(1), cur)
            continue
        mx = _INDEX_RE.search(line)
        if mx:
            cur.index = mx.group(1)
            continue
        # First non-empty, non-keyword line after the Pos line → Bezeichnung.
        s = line.strip()
        if s and cur.bezeichnung is None and not s.lower().startswith("teppich"):
            cur.bezeichnung = s
    _flush(cur)

    if not pl.positions:
        pl.warnings.append("no positions parsed")
    return pl


async def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Run `pdftotext -layout <pdf> -` and return stdout text (async subprocess)."""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.pdf"
        src.write_bytes(pdf_bytes)
        proc = await asyncio.create_subprocess_exec(
            "pdftotext", "-layout", str(src), "-",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            raise ValueError(f"pdftotext failed: {err.decode('utf-8', 'replace')[-500:]}")
        return out.decode("utf-8", "replace")


async def parse_lieferschein(pdf_bytes: bytes) -> ParsedLieferschein:
    return parse_lieferschein_text(await extract_pdf_text(pdf_bytes))
```

- [ ] **Step 5: Run the test**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_lieferschein.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/atr_lieferschein.py backend/tests/fixtures/atr/lieferschein_sample.txt backend/tests/test_atr_lieferschein.py
git commit -m "feat(atr): Lieferschein PDF/text parser"
```

---

## Task 3: Catalog matcher

**Files:**
- Create: `backend/app/services/atr_match.py`
- Test: `backend/tests/test_atr_match.py`

**Interfaces:**
- Consumes: `ParsedLieferschein`, `ParsedPosition`; `AtrPart`.
- Produces: dataclasses `MatchedItem`, `MatchedDelivery`; `async match_positions(db: AsyncSession, parsed: ParsedLieferschein, source_filename: str) -> MatchedDelivery`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_match.py
import pytest

from app.services.atr_lieferschein import parse_lieferschein_text
from app.services.atr_match import match_positions
from tests._auth import ADMIN_UUID, mint  # noqa: F401 (ensures _auth importable)


async def _seed_part(client):
    # create a catalog part for VR11S1010016000 via the Phase A endpoint
    await client.post("/api/atr/parts",
                      headers={"Authorization": f"Bearer {mint(ADMIN_UUID)}"},
                      json={"part_number": "VR11S 1010 016 000",
                            "part_name": "CARPET EMERGENCY EXIT HATCH",
                            "drawing_number_issue": "VR11S 1010-10/D",
                            "default_weight_kg": "0.413", "category": "CARPET",
                            "po_pos": "050"})


async def test_match_and_unmatched(client):
    await _seed_part(client)
    text = (
        "Nr. 20189798\nDatum 08.06.2026\n"
        "1 6060 1 STK\nCARPET EMERG. EXIT HATCH\nBauteil-Index: D\n"
        "Ihre Nr. VR11S1010016000\nAuftrag Nr. 1024738 / 5\n"
        "Bestelldaten 4501119979/A350/CCRC/MSN830/6-Bett\n"
        "2 9999 1 STK\nUNKNOWN PART\nIhre Nr. VR11S9999999999\n"
        "Auftrag Nr. 1024738 / 9\nBestelldaten 4501119979/A350/CCRC/MSN830/6-Bett\n"
    )
    parsed = parse_lieferschein_text(text)
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        md = await match_positions(db, parsed, "LS.pdf")
    assert md.compartment == "CCRC" and md.bed_config == "6"
    assert md.set_title == "SET 6 BED CCRC"
    assert md.po_number == "4501119979"
    matched = [i for i in md.items if i.match_status == "matched"]
    unmatched = [i for i in md.items if i.match_status == "unmatched"]
    assert len(matched) == 1 and len(unmatched) == 1
    m = matched[0]
    assert m.part_name == "CARPET EMERGENCY EXIT HATCH"
    assert m.drawing_number_issue == "VR11S 1010-10/D"
    assert str(m.weight_kg) == "0.413"
    assert m.po_pos == "050"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_match.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Write the matcher**

```python
# backend/app/services/atr_match.py
"""Match Lieferschein positions against the ATR catalog (Phase B)."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AtrPart
from app.services.atr_lieferschein import ParsedLieferschein


@dataclass
class MatchedItem:
    pos: int | None
    supplier_article_code: str | None
    part_number: str | None
    part_number_norm: str | None
    matched_part_id: int | None
    part_name: str | None
    drawing_number_issue: str | None
    category: str | None
    qty: int
    weight_kg: Decimal | None
    po_pos: str | None
    match_status: str
    row_order: int


@dataclass
class MatchedDelivery:
    source_filename: str
    lieferschein_nr: str | None
    datum: str | None
    ba_auftrag: str | None
    po_number: str | None
    ac_programme: str | None
    compartment: str | None
    msn: str | None
    bed_config: str | None
    set_title: str | None
    items: list[MatchedItem] = field(default_factory=list)


async def match_positions(
    db: AsyncSession, parsed: ParsedLieferschein, source_filename: str
) -> MatchedDelivery:
    norms = [p.part_number_norm for p in parsed.positions if p.part_number_norm]
    catalog: dict[str, AtrPart] = {}
    if norms:
        rows = (await db.execute(
            select(AtrPart).where(AtrPart.part_number_norm.in_(norms))
        )).scalars().all()
        catalog = {r.part_number_norm: r for r in rows}

    head = parsed.positions[0] if parsed.positions else None
    compartment = head.compartment if head else None
    bed = head.bed_config if head else None
    set_title = f"SET {bed} BED {compartment}" if bed and compartment else None

    items: list[MatchedItem] = []
    for order, p in enumerate(parsed.positions, start=1):
        part = catalog.get(p.part_number_norm or "")
        if part is not None:
            items.append(MatchedItem(
                pos=p.pos, supplier_article_code=p.supplier_article_code,
                part_number=p.part_number, part_number_norm=p.part_number_norm,
                matched_part_id=part.id, part_name=part.part_name,
                drawing_number_issue=part.drawing_number_issue, category=part.category,
                qty=p.qty, weight_kg=part.default_weight_kg, po_pos=part.po_pos,
                match_status="matched", row_order=order,
            ))
        else:
            items.append(MatchedItem(
                pos=p.pos, supplier_article_code=p.supplier_article_code,
                part_number=p.part_number, part_number_norm=p.part_number_norm,
                matched_part_id=None, part_name=p.bezeichnung,
                drawing_number_issue=None, category=None, qty=p.qty,
                weight_kg=None, po_pos=None, match_status="unmatched", row_order=order,
            ))

    return MatchedDelivery(
        source_filename=source_filename, lieferschein_nr=parsed.lieferschein_nr,
        datum=parsed.datum, ba_auftrag=head.ba_auftrag if head else None,
        po_number=head.po_base if head else None,
        ac_programme=head.ac_programme if head else None,
        compartment=compartment, msn=head.msn if head else None,
        bed_config=bed, set_title=set_title, items=items,
    )
```

- [ ] **Step 4: Run the test**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_match.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/atr_match.py backend/tests/test_atr_match.py
git commit -m "feat(atr): catalog matcher for Lieferschein positions"
```

---

## Task 4: Delivery schemas

**Files:**
- Create: `backend/app/schemas/atr_delivery.py`
- Modify: `backend/app/schemas/__init__.py`
- Test: `backend/tests/test_atr_delivery_schemas.py`

**Interfaces:**
- Produces (from `app.schemas`): `AtrDeliveryItemRead`, `AtrDeliveryItemUpdate`, `AtrDeliveryRead`, `AtrDeliveryUpdate`, `AtrDeliverySummary`, `AtrGenerateManifest`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_delivery_schemas.py
from app.schemas import AtrDeliveryRead, AtrDeliveryItemUpdate


def test_item_update_partial():
    u = AtrDeliveryItemUpdate(weight_kg="1.25")
    assert u.po_pos is None


def test_delivery_read_has_items_field():
    assert "items" in AtrDeliveryRead.model_fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_delivery_schemas.py -v`
Expected: FAIL `ImportError`.

- [ ] **Step 3: Write the schemas**

```python
# backend/app/schemas/atr_delivery.py
"""Pydantic v2 DTOs for ATR deliveries (Phase B)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class AtrDeliveryItemRead(BaseModel):
    id: int
    pos: int | None
    supplier_article_code: str | None
    part_number: str | None
    part_number_norm: str | None
    matched_part_id: int | None
    part_name: str | None
    drawing_number_issue: str | None
    category: str | None
    qty: int
    weight_kg: Decimal | None
    po_pos: str | None
    match_status: str
    row_order: int
    model_config = {"from_attributes": True}


class AtrDeliveryItemUpdate(BaseModel):
    weight_kg: Decimal | None = None
    po_pos: str | None = Field(default=None, max_length=20)
    part_name: str | None = Field(default=None, max_length=200)
    drawing_number_issue: str | None = Field(default=None, max_length=60)
    category: str | None = Field(default=None, max_length=40)


class AtrDeliveryRead(BaseModel):
    id: int
    source_filename: str
    lieferschein_nr: str | None
    datum: date | None
    ba_auftrag: str | None
    po_number: str | None
    ac_programme: str | None
    compartment: str | None
    msn: str | None
    bed_config: str | None
    set_title: str | None
    atr_number: str | None
    container_number: str | None
    weighing_date: date | None
    testing_date: date | None
    qa_signer: str | None
    max_guaranteed_weight_kg: Decimal | None
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[AtrDeliveryItemRead]
    model_config = {"from_attributes": True}


class AtrDeliverySummary(BaseModel):
    id: int
    source_filename: str
    ba_auftrag: str | None
    compartment: str | None
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


class AtrDeliveryUpdate(BaseModel):
    po_number: str | None = Field(default=None, max_length=60)
    set_title: str | None = Field(default=None, max_length=100)
    atr_number: str | None = Field(default=None, max_length=80)
    container_number: str | None = Field(default=None, max_length=40)
    weighing_date: date | None = None
    testing_date: date | None = None
    qa_signer: str | None = Field(default=None, max_length=100)
    max_guaranteed_weight_kg: Decimal | None = None


class AtrGenerateManifest(BaseModel):
    delivery_id: int
    files: list[Literal["atr_xlsx", "atr_pdf", "label_docx"]]
    pdf_available: bool
    unmatched_count: int
    warnings: list[str]
```

Re-export in `backend/app/schemas/__init__.py`:

```python
from app.schemas.atr_delivery import (  # noqa: F401
    AtrDeliveryItemRead, AtrDeliveryItemUpdate, AtrDeliveryRead,
    AtrDeliverySummary, AtrDeliveryUpdate, AtrGenerateManifest,
)
```

- [ ] **Step 4: Run the test**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_delivery_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/atr_delivery.py backend/app/schemas/__init__.py backend/tests/test_atr_delivery_schemas.py
git commit -m "feat(atr): delivery pydantic schemas"
```

---

## Task 5: Delivery router — ingest + review (no generation yet)

**Files:**
- Create: `backend/app/routers/atr_delivery.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_atr_delivery_router.py`, `backend/tests/test_atr_delivery_admin_gate.py`

**Interfaces:**
- Consumes: `parse_lieferschein`, `match_positions`, models, delivery schemas, `ATR_INPUT_DIR` env.
- Produces: router at `/api/atr/deliveries` with `POST /upload`, `GET /input-files`, `POST /input-files/process`, `GET ``, `GET /{id}`, `PATCH /{id}`, `PATCH /{id}/items/{item_id}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_delivery_router.py
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


def _pdf_like_lieferschein() -> bytes:
    # A real .pdf is needed because the upload path runs pdftotext. Build a
    # tiny one-page PDF whose text layer contains a Lieferschein position.
    text = ("LIEFERSCHEIN Nr. 20189798 Datum 08.06.2026 "
            "1 6060 1 STK CARPET EMERG. EXIT HATCH Bauteil-Index: D "
            "Ihre Nr. VR11S1010016000 Auftrag Nr. 1024738 / 5 "
            "Bestelldaten 4501119979/A350/CCRC/MSN830/6-Bett")
    # Minimal PDF with a text object — see fixture builder in Step 3 note.
    from tests._atr_pdf import make_text_pdf
    return make_text_pdf(text)


async def test_upload_creates_draft_with_items(client):
    files = {"file": ("LS.pdf", _pdf_like_lieferschein(), "application/pdf")}
    r = await client.post("/api/atr/deliveries/upload", headers=_auth(), files=files)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["compartment"] == "CCRC"
    assert len(body["items"]) >= 1
    did = body["id"]

    # patch header
    r = await client.patch(f"/api/atr/deliveries/{did}", headers=_auth(),
                           json={"container_number": "AK111000"})
    assert r.json()["container_number"] == "AK111000"

    # patch an item
    iid = body["items"][0]["id"]
    r = await client.patch(f"/api/atr/deliveries/{did}/items/{iid}", headers=_auth(),
                           json={"weight_kg": "0.420"})
    assert r.json()["weight_kg"] == "0.420"

    # list + get
    assert any(d["id"] == did for d in (await client.get("/api/atr/deliveries", headers=_auth())).json())
    assert (await client.get(f"/api/atr/deliveries/{did}", headers=_auth())).status_code == 200


async def test_input_files_empty_when_unset(client):
    r = await client.get("/api/atr/deliveries/input-files", headers=_auth())
    assert r.status_code == 200
    assert r.json() == {"configured": False, "files": []}
```

> The PDF builder helper `tests/_atr_pdf.make_text_pdf(text)` produces a minimal valid single-page PDF with an embedded text layer that `pdftotext` can extract. Create it in Step 3.

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_delivery_router.py -v`
Expected: FAIL (404 / missing module).

- [ ] **Step 3: Write the PDF test helper**

```python
# backend/tests/_atr_pdf.py
"""Minimal single-page PDF with a text layer pdftotext can read — test-only."""


def make_text_pdf(text: str) -> bytes:
    esc = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    objs = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>")
    stream = (b"BT /F1 10 Tf 36 750 Td (" + esc.encode("latin-1", "replace") + b") Tj ET")
    objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += (b"trailer\n<< /Size " + str(len(objs) + 1).encode() +
            b" /Root 1 0 R >>\nstartxref\n" + str(xref_pos).encode() + b"\n%%EOF")
    return bytes(out)
```

- [ ] **Step 4: Write the router**

```python
# backend/app/routers/atr_delivery.py
"""/api/atr/deliveries/* — admin-gated Lieferschein ingest + review (Phase B).

Generation endpoints are added in Wave 2.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import AtrDelivery, AtrDeliveryItem
from app.schemas import (
    AtrDeliveryItemRead, AtrDeliveryItemUpdate, AtrDeliveryRead,
    AtrDeliverySummary, AtrDeliveryUpdate,
)
from app.security.directus_auth import get_current_user, require_admin
from app.services.atr_lieferschein import parse_lieferschein
from app.services.atr_match import MatchedDelivery, match_positions

router = APIRouter(
    prefix="/api/atr/deliveries", tags=["atr"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)


def _parse_datum(s: str | None):
    if not s:
        return None
    try:
        from datetime import datetime as _dt
        return _dt.strptime(s, "%d.%m.%Y").date()
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
    from app.models import AtrTemplate
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
    await db.refresh(row)
    return row


async def _get(db: AsyncSession, delivery_id: int) -> AtrDelivery:
    row = (await db.execute(
        select(AtrDelivery).where(AtrDelivery.id == delivery_id)
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
    parsed = await parse_lieferschein(target.read_bytes())
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
    await db.refresh(row)
    return row


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
```

Register in `backend/app/main.py`: `from app.routers.atr_delivery import router as atr_delivery_router` + `app.include_router(atr_delivery_router)`.

- [ ] **Step 5: Write the admin-gate test**

```python
# backend/tests/test_atr_delivery_admin_gate.py
from fastapi.routing import APIRoute

from app.main import app
from app.security.directus_auth import require_admin
from tests._auth import VIEWER_UUID, mint


def _walk(deps):
    out = []
    for d in deps:
        out.append(d.call); out.extend(_walk(d.dependencies))
    return out


def test_delivery_routes_gated():
    routes = [r for r in app.routes
              if isinstance(r, APIRoute) and r.path.startswith("/api/atr/deliveries")]
    assert len(routes) >= 7
    for r in routes:
        assert require_admin in _walk(r.dependant.dependencies), r.path


async def test_viewer_403(client):
    r = await client.get("/api/atr/deliveries",
                         headers={"Authorization": f"Bearer {mint(VIEWER_UUID)}"})
    assert r.status_code == 403
```

- [ ] **Step 6: Run the tests**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_delivery_router.py tests/test_atr_delivery_admin_gate.py tests/test_admin_gate_audit.py -v`
Expected: the two new files PASS; `test_admin_gate_audit.py` keeps its pre-existing state (the atr deliveries routes must NOT add new violations).

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/atr_delivery.py backend/app/main.py backend/tests/test_atr_delivery_router.py backend/tests/test_atr_delivery_admin_gate.py backend/tests/_atr_pdf.py
git commit -m "feat(atr): delivery ingest + review router (upload, input-files, list/get/patch)"
```

---

# Wave 2 — Generation

## Task 6: Generation infra (libreoffice-calc + python-docx)

**Files:**
- Modify: `backend/Dockerfile`
- Modify: `backend/requirements.txt`
- Modify: `docker-compose.yml`

**Interfaces:**
- Produces: `soffice` able to convert xlsx→pdf; `docx` importable in the api container; `ATR_INPUT_DIR` env wired.

- [ ] **Step 1: Edit the Dockerfile**

In `backend/Dockerfile`, add `libreoffice-calc \` to the `apt-get install` list (immediately after `libreoffice-impress \`).

- [ ] **Step 2: Edit requirements**

In `backend/requirements.txt`, add a line: `python-docx==1.1.2`.

- [ ] **Step 3: Wire ATR_INPUT_DIR (optional input-dir mode)**

In `docker-compose.yml` under the `api` service `environment:` block, add:
```yaml
      ATR_INPUT_DIR: ${ATR_INPUT_DIR:-}
```
(Leaving it unset disables the input-dir mode — the dev/Phase-C operator can point it at a mounted directory later.)

- [ ] **Step 4: Rebuild the api image and verify**

Run:
```bash
docker compose build api
docker compose up -d api
docker compose exec -T api python -c "import docx; print('docx', docx.__version__)"
docker compose exec -T api sh -lc 'python -c "from openpyxl import Workbook; wb=Workbook(); wb.active[\"A1\"]=\"hi\"; wb.save(\"/tmp/t.xlsx\")"; soffice --headless --convert-to pdf --outdir /tmp /tmp/t.xlsx >/dev/null 2>&1; test -s /tmp/t.pdf && echo "xlsx->pdf OK"'
```
Expected: `docx 1.1.2` and `xlsx->pdf OK`.

- [ ] **Step 5: Commit**

```bash
git add backend/Dockerfile backend/requirements.txt docker-compose.yml
git commit -m "build(atr): add libreoffice-calc + python-docx, wire ATR_INPUT_DIR"
```

---

## Task 7: ATR xlsx generator

**Files:**
- Create: `backend/app/services/atr_generate_xlsx.py`
- Test: `backend/tests/test_atr_generate_xlsx.py`

**Interfaces:**
- Consumes: `AtrDelivery`, `AtrDeliveryItem`, `AtrTemplate.structure_xlsx`.
- Produces: `build_atr_xlsx(template_bytes: bytes, delivery: AtrDelivery, items: list[AtrDeliveryItem]) -> bytes`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_generate_xlsx.py
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from openpyxl import load_workbook

from app.services.atr_generate_xlsx import build_atr_xlsx
from tests._atr_fixtures import build_atr_workbook_bytes  # Phase A fixture builder


def _item(**kw):
    base = dict(pos=1, supplier_article_code="6060", part_number="VR11S 1010 016 000",
                part_number_norm="111010016000", part_name="CARPET EMERGENCY EXIT HATCH",
                drawing_number_issue="VR11S 1010-10/D", category="CARPET", qty=1,
                weight_kg=Decimal("0.413"), po_pos="050", match_status="matched", row_order=1)
    base.update(kw)
    return SimpleNamespace(**base)


def _delivery(**kw):
    base = dict(set_title="SET 6 BED CCRC", po_number="4501119979", msn="830",
                ba_auftrag="1024738", atr_number="ACM-A350CRC-ATR-4545-01",
                qa_signer="Cordula Kesseler i.A.", max_guaranteed_weight_kg=Decimal("211"))
    base.update(kw)
    return SimpleNamespace(**base)


def test_build_writes_header_rows_and_total():
    items = [_item(), _item(pos=2, supplier_article_code="11395",
                            part_number="VR11S 1010 048 000", part_number_norm="111010048000",
                            part_name="CARPET BEDS FWD", drawing_number_issue="VR11S 1010-27/A",
                            weight_kg=Decimal("1.218"), po_pos="300", row_order=2)]
    out = build_atr_xlsx(build_atr_workbook_bytes(), _delivery(), items)
    wb = load_workbook(BytesIO(out))
    ws = [w for w in wb.worksheets if w.sheet_state == "visible"][0]
    assert ws["A11"].value == "SET 6 BED CCRC"
    # the two part rows are present somewhere in the table region
    pns = [ws.cell(r, 3).value for r in range(14, ws.max_row + 1)]
    assert "VR11S 1010 016 000" in pns and "VR11S 1010 048 000" in pns
    # a "Total weight" label exists with the summed value 1.631
    totals = [(r, ws.cell(r, 8).value) for r in range(14, ws.max_row + 1)
              if str(ws.cell(r, 6).value or "").lower().startswith("total")]
    assert totals and abs(float(totals[0][1]) - 1.631) < 0.001


def test_unmatched_row_is_red():
    items = [_item(match_status="unmatched", drawing_number_issue=None,
                   weight_kg=None, part_name="UNKNOWN")]
    out = build_atr_xlsx(build_atr_workbook_bytes(), _delivery(), items)
    wb = load_workbook(BytesIO(out))
    ws = [w for w in wb.worksheets if w.sheet_state == "visible"][0]
    red_rows = [r for r in range(14, ws.max_row + 1)
                if ws.cell(r, 3).value == "VR11S 1010 016 000"
                and (ws.cell(r, 3).fill.fgColor.rgb or "").endswith("FF0000")]
    assert red_rows, "unmatched part row should carry a red fill"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_generate_xlsx.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Write the generator**

```python
# backend/app/services/atr_generate_xlsx.py
"""Fill the stored ATR template (frame) with a delivery's matched rows (Phase B).

Template-as-frame: keep the template's header block / table header / totals /
certification formatting; rewrite the part-table region with the delivery items
(grouped by category), copying cell style from a template part row. Unmatched
items get a red fill so the operator fixes them in Excel.
"""
from __future__ import annotations

from copy import copy
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter

_RED = PatternFill(start_color="FFFF0000", end_color="FFFF0000", fill_type="solid")
_TABLE_HEADER_ROW = 13
_FIRST_PART_ROW = 14
_NCOLS = 14  # A..N


def _visible_sheet(wb):
    vis = [w for w in wb.worksheets if w.sheet_state == "visible"]
    if len(vis) != 1:
        raise ValueError(f"expected one visible sheet, found {len(vis)}")
    return vis[0]


def _find_totals_row(ws) -> int:
    for r in range(_FIRST_PART_ROW, ws.max_row + 1):
        f = ws.cell(r, 6).value
        if f and "total" in str(f).lower():
            return r
    return ws.max_row + 1


def _capture_row_styles(ws, row: int) -> list:
    return [copy(ws.cell(row, c)._style) for c in range(1, _NCOLS + 1)]


def build_atr_xlsx(template_bytes: bytes, delivery, items) -> bytes:
    wb = load_workbook(BytesIO(template_bytes))
    ws = _visible_sheet(wb)

    # --- header block (template defaults stay; per-delivery values overwrite) ---
    if delivery.set_title is not None:
        ws["A11"] = delivery.set_title
    if delivery.po_number is not None:
        ws["G1"] = delivery.po_number
    if delivery.msn is not None:
        ws["G2"] = delivery.msn
    if delivery.ba_auftrag is not None:
        ws["D9"] = delivery.ba_auftrag
    if getattr(delivery, "weighing_date", None):
        ws["C12"] = str(delivery.weighing_date)
    if getattr(delivery, "testing_date", None):
        ws["L12"] = str(delivery.testing_date)
    # Doc-No lives in the print header (not a cell).
    if delivery.atr_number:
        ws.oddHeader.right.text = f"Doc-No.: {delivery.atr_number}"

    # --- capture reference styles BEFORE mutating the region ---
    part_style = _capture_row_styles(ws, _FIRST_PART_ROW + 1)  # a part row
    section_style = _capture_row_styles(ws, _FIRST_PART_ROW)   # a section header row

    totals_row = _find_totals_row(ws)
    region_count = max(0, totals_row - _FIRST_PART_ROW)

    # group items by category in first-seen order
    grouped: list[tuple[str | None, list]] = []
    index: dict[str | None, int] = {}
    for it in items:
        cat = it.category
        if cat not in index:
            index[cat] = len(grouped)
            grouped.append((cat, []))
        grouped[index[cat]][1].append(it)

    # rows we will write: one section header per category + one per item
    out_rows = sum(1 + len(lst) for _, lst in grouped)

    # clear the example region and resize it to out_rows
    if region_count:
        ws.delete_rows(_FIRST_PART_ROW, region_count)
    if out_rows:
        ws.insert_rows(_FIRST_PART_ROW, out_rows)

    r = _FIRST_PART_ROW
    total_weight = Decimal("0")
    for cat, lst in grouped:
        # section header row
        for c in range(1, _NCOLS + 1):
            ws.cell(r, c)._style = copy(section_style[c - 1])
        ws.cell(r, 1, cat or "")
        r += 1
        for it in lst:
            for c in range(1, _NCOLS + 1):
                ws.cell(r, c)._style = copy(part_style[c - 1])
            ws.cell(r, 1, it.po_pos or "")
            ws.cell(r, 2, it.supplier_article_code or "")
            ws.cell(r, 3, it.part_number or "")
            ws.cell(r, 4, it.part_name or "")
            ws.cell(r, 5, "N/A")
            ws.cell(r, 6, it.drawing_number_issue or "")
            ws.cell(r, 7, it.qty)
            if it.weight_kg is not None:
                ws.cell(r, 8, float(it.weight_kg))
                total_weight += it.weight_kg
            for c, mark in zip(range(9, 14), ("P", "P", "P", "P", "P")):
                ws.cell(r, c, mark)
            ws.cell(r, 14, "OK")
            if it.match_status != "matched":
                for c in range(1, _NCOLS + 1):
                    ws.cell(r, c).fill = _RED
            r += 1

    # totals block shifted down by (out_rows - region_count + region_count) — re-find it
    new_totals_row = _find_totals_row(ws)
    if new_totals_row <= ws.max_row:
        ws.cell(new_totals_row, 8, float(total_weight))
        # Max. Guaranteed weight on the next totals label row, if present
        for rr in range(new_totals_row, min(new_totals_row + 4, ws.max_row + 1)):
            if "max" in str(ws.cell(rr, 6).value or "").lower() and delivery.max_guaranteed_weight_kg is not None:
                ws.cell(rr, 8, float(delivery.max_guaranteed_weight_kg))

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()
```

> Note for the implementer: openpyxl's `_style` copy preserves font/border/fill from the template row. The `get_column_letter` import is available if you prefer letter addressing; numeric `cell(r, c)` is used here. Verify the produced file opens in Excel/LibreOffice without repair prompts — if `insert_rows` disturbs a merged range in the totals/cert block, unmerge those ranges before delete/insert and re-merge after (the test covers the part-row + total assertions; add an unmerge/re-merge step only if the produced file warns).

- [ ] **Step 4: Run the test**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_generate_xlsx.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/atr_generate_xlsx.py backend/tests/test_atr_generate_xlsx.py
git commit -m "feat(atr): ATR xlsx generator (template-as-frame, red-flag unmatched)"
```

---

## Task 8: xlsx → PDF conversion

**Files:**
- Modify: `backend/app/services/atr_generate_xlsx.py`
- Test: `backend/tests/test_atr_xlsx_to_pdf.py`

**Interfaces:**
- Produces: `async convert_xlsx_to_pdf(xlsx_bytes: bytes) -> bytes` (raises `RuntimeError` on failure/timeout).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_xlsx_to_pdf.py
import pytest

from app.services.atr_generate_xlsx import convert_xlsx_to_pdf
from tests._atr_fixtures import build_atr_workbook_bytes


async def test_xlsx_to_pdf_smoke():
    pdf = await convert_xlsx_to_pdf(build_atr_workbook_bytes())
    assert pdf[:5] == b"%PDF-" and len(pdf) > 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_xlsx_to_pdf.py -v`
Expected: FAIL (`convert_xlsx_to_pdf` undefined).

- [ ] **Step 3: Add the converter**

Append to `backend/app/services/atr_generate_xlsx.py` (add imports `asyncio`, `shutil`, `uuid as _uuid`, `from pathlib import Path`):

```python
import asyncio
import shutil
import uuid as _uuid
from pathlib import Path

# Serialize LibreOffice across the single-worker api container (mirror signage_pptx).
_LO_SEMAPHORE = asyncio.Semaphore(1)
_LO_TIMEOUT_S = 60


async def convert_xlsx_to_pdf(xlsx_bytes: bytes) -> bytes:
    async with _LO_SEMAPHORE:
        tempdir = Path(f"/tmp/atr_{_uuid.uuid4()}")
        lo_profile = Path(f"/tmp/lo_{_uuid.uuid4()}")
        try:
            tempdir.mkdir(parents=True, exist_ok=True)
            src = tempdir / "atr.xlsx"
            src.write_bytes(xlsx_bytes)
            proc = await asyncio.create_subprocess_exec(
                "soffice", "--headless",
                f"-env:UserInstallation=file://{lo_profile}",
                "--convert-to", "pdf", "--outdir", str(tempdir), str(src),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, err = await asyncio.wait_for(proc.communicate(), timeout=_LO_TIMEOUT_S)
            except asyncio.TimeoutError as exc:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                raise RuntimeError("xlsx->pdf conversion timed out") from exc
            if proc.returncode != 0:
                raise RuntimeError(
                    f"soffice failed: {err.decode('utf-8', 'replace')[-500:]}"
                )
            try:
                pdf_path = next(tempdir.glob("*.pdf"))
            except StopIteration as exc:
                raise RuntimeError("soffice produced no PDF") from exc
            return pdf_path.read_bytes()
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)
            shutil.rmtree(lo_profile, ignore_errors=True)
```

- [ ] **Step 4: Run the test**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_xlsx_to_pdf.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/atr_generate_xlsx.py backend/tests/test_atr_xlsx_to_pdf.py
git commit -m "feat(atr): xlsx->pdf via LibreOffice headless (async, serialized)"
```

---

## Task 9: Containerbeschriftung (.docx) generator

**Files:**
- Create: `backend/app/services/atr_generate_docx.py`
- Test: `backend/tests/test_atr_generate_docx.py`

**Interfaces:**
- Produces: `build_containerbeschriftung(delivery, items) -> bytes`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_generate_docx.py
from io import BytesIO
from types import SimpleNamespace

from docx import Document

from app.services.atr_generate_docx import build_containerbeschriftung


def _it(po_pos):
    return SimpleNamespace(po_pos=po_pos)


def test_label_lines():
    delivery = SimpleNamespace(ba_auftrag="1024738", po_number="4501119979",
                               ac_programme="A350", msn="830", container_number="AK111XXX")
    items = [_it("300"), _it("050"), _it("340")]
    out = build_containerbeschriftung(delivery, items)
    doc = Document(BytesIO(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "BA 1024738" in text
    assert "PO 4501119979" in text
    assert "Pos. 050, 300, 340" in text  # sorted, comma-joined
    assert "A350 Teppiche MSN 830" in text
    assert "Container AK111XXX" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_generate_docx.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Write the generator**

```python
# backend/app/services/atr_generate_docx.py
"""Containerbeschriftung (.docx) generator (ATR Phase B)."""
from __future__ import annotations

from io import BytesIO

from docx import Document
from docx.shared import Pt


def build_containerbeschriftung(delivery, items) -> bytes:
    pos_list = sorted({(it.po_pos or "").strip() for it in items if (it.po_pos or "").strip()})
    lines = [
        f"BA {delivery.ba_auftrag or ''}".rstrip(),
        f"PO {delivery.po_number or ''}".rstrip(),
        f"Pos. {', '.join(pos_list)}",
        f"{delivery.ac_programme or ''} Teppiche MSN {delivery.msn or ''}".strip(),
        f"Container {delivery.container_number or ''}".rstrip(),
    ]
    doc = Document()
    for line in lines:
        p = doc.add_paragraph()
        run = p.add_run(line)
        run.bold = True
        run.font.size = Pt(20)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()
```

- [ ] **Step 4: Run the test**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_generate_docx.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/atr_generate_docx.py backend/tests/test_atr_generate_docx.py
git commit -m "feat(atr): Containerbeschriftung docx generator"
```

---

## Task 10: Generate + download endpoints

**Files:**
- Modify: `backend/app/routers/atr_delivery.py`
- Test: `backend/tests/test_atr_delivery_generate.py`

**Interfaces:**
- Consumes: `build_atr_xlsx`, `convert_xlsx_to_pdf`, `build_containerbeschriftung`, `AtrTemplate.structure_xlsx`, `AtrGenerateManifest`.
- Produces: `POST /{id}/generate` (→ `AtrGenerateManifest`), `GET /{id}/files/{kind}` (binary download).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_delivery_generate.py
from tests._atr_fixtures import build_atr_workbook_bytes
from tests._atr_pdf import make_text_pdf
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


async def _set_structure(client):
    files = {"file": ("t.xlsx", build_atr_workbook_bytes(),
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    await client.post("/api/atr/template/structure", headers=_auth(), files=files)


async def _draft(client):
    text = ("LIEFERSCHEIN Nr. 20189798 Datum 08.06.2026 "
            "1 6060 1 STK CARPET EMERG. EXIT HATCH Bauteil-Index: D "
            "Ihre Nr. VR11S1010016000 Auftrag Nr. 1024738 / 5 "
            "Bestelldaten 4501119979/A350/CCRC/MSN830/6-Bett")
    files = {"file": ("LS.pdf", make_text_pdf(text), "application/pdf")}
    return (await client.post("/api/atr/deliveries/upload", headers=_auth(), files=files)).json()


async def test_generate_and_download(client):
    await _set_structure(client)
    d = await _draft(client)
    did = d["id"]
    r = await client.post(f"/api/atr/deliveries/{did}/generate", headers=_auth(),
                          json={})
    assert r.status_code == 200, r.text
    man = r.json()
    assert "atr_xlsx" in man["files"] and "label_docx" in man["files"]
    # downloads
    rx = await client.get(f"/api/atr/deliveries/{did}/files/atr_xlsx", headers=_auth())
    assert rx.status_code == 200 and rx.content[:2] == b"PK"  # xlsx is a zip
    rd = await client.get(f"/api/atr/deliveries/{did}/files/label_docx", headers=_auth())
    assert rd.status_code == 200 and rd.content[:2] == b"PK"
    if man["pdf_available"]:
        rp = await client.get(f"/api/atr/deliveries/{did}/files/atr_pdf", headers=_auth())
        assert rp.status_code == 200 and rp.content[:5] == b"%PDF-"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_delivery_generate.py -v`
Expected: FAIL (404 — endpoints missing).

- [ ] **Step 3: Add the endpoints**

Append to `backend/app/routers/atr_delivery.py` (add imports: `import logging`; `from fastapi import Response`; `from app.models import AtrTemplate`; `from app.schemas import AtrGenerateManifest`; `from app.services.atr_generate_xlsx import build_atr_xlsx, convert_xlsx_to_pdf`; `from app.services.atr_generate_docx import build_containerbeschriftung`; `log = logging.getLogger(__name__)`):

```python
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
```

- [ ] **Step 4: Run the test**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_delivery_generate.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full backend atr suite**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_*.py -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/atr_delivery.py backend/tests/test_atr_delivery_generate.py
git commit -m "feat(atr): generate + download ATR xlsx/pdf + label docx"
```

---

# Wave 3 — Review UI

## Task 11: Frontend delivery API + i18n

**Files:**
- Modify: `frontend/src/lib/atrApi.ts`
- Modify: `frontend/src/locales/en.json`, `frontend/src/locales/de.json`

**Interfaces:**
- Produces: TS types `AtrDeliveryItem`, `AtrDelivery`, `AtrDeliverySummary`, `AtrGenerateManifest`, `AtrInputFiles`; fetchers `uploadLieferschein`, `fetchInputFiles`, `processInputFile`, `fetchDeliveries`, `fetchDelivery`, `updateDelivery`, `updateDeliveryItem`, `generateDelivery`, `atrFileUrl`.

- [ ] **Step 1: Append to `frontend/src/lib/atrApi.ts`**

```typescript
export interface AtrDeliveryItem {
  id: number; pos: number | null; supplier_article_code: string | null;
  part_number: string | null; part_number_norm: string | null;
  matched_part_id: number | null; part_name: string | null;
  drawing_number_issue: string | null; category: string | null; qty: number;
  weight_kg: string | null; po_pos: string | null; match_status: string; row_order: number;
}
export interface AtrDelivery {
  id: number; source_filename: string; lieferschein_nr: string | null; datum: string | null;
  ba_auftrag: string | null; po_number: string | null; ac_programme: string | null;
  compartment: string | null; msn: string | null; bed_config: string | null;
  set_title: string | null; atr_number: string | null; container_number: string | null;
  weighing_date: string | null; testing_date: string | null; qa_signer: string | null;
  max_guaranteed_weight_kg: string | null; status: string;
  created_at: string; updated_at: string; items: AtrDeliveryItem[];
}
export interface AtrDeliverySummary {
  id: number; source_filename: string; ba_auftrag: string | null;
  compartment: string | null; status: string; created_at: string;
}
export interface AtrGenerateManifest {
  delivery_id: number; files: string[]; pdf_available: boolean;
  unmatched_count: number; warnings: string[];
}
export interface AtrInputFiles { configured: boolean; files: string[]; }

export async function uploadLieferschein(file: File): Promise<AtrDelivery> {
  const fd = new FormData(); fd.append("file", file);
  return apiClient<AtrDelivery>("/api/atr/deliveries/upload", { method: "POST", body: fd });
}
export async function fetchInputFiles(): Promise<AtrInputFiles> {
  return apiClient<AtrInputFiles>("/api/atr/deliveries/input-files");
}
export async function processInputFile(filename: string): Promise<AtrDelivery> {
  return apiClient<AtrDelivery>("/api/atr/deliveries/input-files/process", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  });
}
export async function fetchDeliveries(): Promise<AtrDeliverySummary[]> {
  return apiClient<AtrDeliverySummary[]>("/api/atr/deliveries");
}
export async function fetchDelivery(id: number): Promise<AtrDelivery> {
  return apiClient<AtrDelivery>(`/api/atr/deliveries/${id}`);
}
export async function updateDelivery(id: number, body: Partial<AtrDelivery>): Promise<AtrDelivery> {
  return apiClient<AtrDelivery>(`/api/atr/deliveries/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
}
export async function updateDeliveryItem(
  did: number, iid: number, body: Partial<AtrDeliveryItem>,
): Promise<AtrDeliveryItem> {
  return apiClient<AtrDeliveryItem>(`/api/atr/deliveries/${did}/items/${iid}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
}
export async function generateDelivery(id: number): Promise<AtrGenerateManifest> {
  return apiClient<AtrGenerateManifest>(`/api/atr/deliveries/${id}/generate`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
  });
}
export function atrFileUrl(id: number, kind: "atr_xlsx" | "atr_pdf" | "label_docx"): string {
  return `/api/atr/deliveries/${id}/files/${kind}`;
}
```

- [ ] **Step 2: Add flat i18n keys**

Add these flat keys (NOT nested — `keySeparator` is false) into `frontend/src/locales/en.json`:

```json
"atr.deliveries.heading": "Deliveries",
"atr.deliveries.upload": "Upload Lieferschein",
"atr.deliveries.from_folder": "From input folder",
"atr.deliveries.process": "Process",
"atr.deliveries.col.source": "Source file",
"atr.deliveries.col.ba": "BA",
"atr.deliveries.col.status": "Status",
"atr.deliveries.col.created": "Created",
"atr.deliveries.open": "Open",
"atr.deliveries.review.heading": "Review delivery",
"atr.deliveries.field.atr_number": "ATR number",
"atr.deliveries.field.container_number": "Container number",
"atr.deliveries.field.set_title": "Set title",
"atr.deliveries.field.po_number": "PO number",
"atr.deliveries.field.weighing_date": "Weighing date",
"atr.deliveries.field.testing_date": "Testing date",
"atr.deliveries.field.qa_signer": "QA signer",
"atr.deliveries.field.max_weight": "Max. guaranteed weight",
"atr.deliveries.item.part_number": "Part number",
"atr.deliveries.item.name": "Part name",
"atr.deliveries.item.drawing": "Drawing / Issue",
"atr.deliveries.item.weight": "Weight [kg]",
"atr.deliveries.item.po_pos": "PO Pos",
"atr.deliveries.item.unmatched": "Unmatched",
"atr.deliveries.save": "Save",
"atr.deliveries.generate": "Generate",
"atr.deliveries.download_xlsx": "Download .xlsx",
"atr.deliveries.download_pdf": "Download PDF",
"atr.deliveries.download_docx": "Download label",
```

Add the German mirror into `frontend/src/locales/de.json` (same keys, German values), e.g. `"atr.deliveries.heading": "Lieferungen"`, `"atr.deliveries.upload": "Lieferschein hochladen"`, `"atr.deliveries.from_folder": "Aus Eingangsordner"`, `"atr.deliveries.process": "Verarbeiten"`, `"atr.deliveries.col.source": "Quelldatei"`, `"atr.deliveries.col.ba": "BA"`, `"atr.deliveries.col.status": "Status"`, `"atr.deliveries.col.created": "Erstellt"`, `"atr.deliveries.open": "Öffnen"`, `"atr.deliveries.review.heading": "Lieferung prüfen"`, `"atr.deliveries.field.atr_number": "ATR-Nummer"`, `"atr.deliveries.field.container_number": "Containernummer"`, `"atr.deliveries.field.set_title": "Set-Titel"`, `"atr.deliveries.field.po_number": "PO-Nummer"`, `"atr.deliveries.field.weighing_date": "Wiegedatum"`, `"atr.deliveries.field.testing_date": "Prüfdatum"`, `"atr.deliveries.field.qa_signer": "QS-Unterzeichner"`, `"atr.deliveries.field.max_weight": "Max. Garantiegewicht"`, `"atr.deliveries.item.part_number": "Teilenummer"`, `"atr.deliveries.item.name": "Bezeichnung"`, `"atr.deliveries.item.drawing": "Zeichnung / Index"`, `"atr.deliveries.item.weight": "Gewicht [kg]"`, `"atr.deliveries.item.po_pos": "PO Pos"`, `"atr.deliveries.item.unmatched": "Nicht zugeordnet"`, `"atr.deliveries.save": "Speichern"`, `"atr.deliveries.generate": "Generieren"`, `"atr.deliveries.download_xlsx": "Excel herunterladen"`, `"atr.deliveries.download_pdf": "PDF herunterladen"`, `"atr.deliveries.download_docx": "Etikett herunterladen"`.

- [ ] **Step 3: Verify**

Run:
```bash
cd frontend && node -e "JSON.parse(require('fs').readFileSync('src/locales/en.json','utf8')); JSON.parse(require('fs').readFileSync('src/locales/de.json','utf8')); console.log('json ok')"
cd frontend && npx tsc --noEmit
```
Expected: `json ok`, tsc clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/atrApi.ts frontend/src/locales/en.json frontend/src/locales/de.json
git commit -m "feat(atr): frontend delivery api + i18n keys"
```

---

## Task 12: Deliveries list page

**Files:**
- Create: `frontend/src/pages/AtrDeliveriesPage.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/pages/__tests__/AtrDeliveriesPage.test.tsx`

**Interfaces:**
- Consumes: `fetchDeliveries`, `uploadLieferschein`, `fetchInputFiles`, `processInputFile`.

- [ ] **Step 1: Write the page**

```tsx
// frontend/src/pages/AtrDeliveriesPage.tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { toast } from "sonner";
import {
  fetchDeliveries, uploadLieferschein, fetchInputFiles, processInputFile,
} from "@/lib/atrApi";

export function AtrDeliveriesPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [, setLocation] = useLocation();
  const { data: deliveries } = useQuery({ queryKey: ["atr", "deliveries"], queryFn: fetchDeliveries });
  const { data: input } = useQuery({ queryKey: ["atr", "input-files"], queryFn: fetchInputFiles });
  const [busy, setBusy] = useState(false);
  const [picked, setPicked] = useState("");

  async function onUpload(file: File) {
    setBusy(true);
    try {
      const d = await uploadLieferschein(file);
      qc.invalidateQueries({ queryKey: ["atr", "deliveries"] });
      setLocation(`/atr/deliveries/${d.id}`);
    } catch (e) { toast.error(String(e)); } finally { setBusy(false); }
  }
  async function onProcess() {
    if (!picked) return;
    setBusy(true);
    try {
      const d = await processInputFile(picked);
      qc.invalidateQueries({ queryKey: ["atr", "deliveries"] });
      setLocation(`/atr/deliveries/${d.id}`);
    } catch (e) { toast.error(String(e)); } finally { setBusy(false); }
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-6">
      <h1 className="text-xl font-semibold mb-4">{t("atr.deliveries.heading")}</h1>
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <label className="px-3 py-2 border rounded cursor-pointer">
          {t("atr.deliveries.upload")}
          <input type="file" accept=".pdf" className="hidden" disabled={busy}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); }} />
        </label>
        {input?.configured && (
          <div className="flex items-center gap-2">
            <select className="border rounded px-2 py-2" value={picked}
              onChange={(e) => setPicked(e.target.value)} aria-label={t("atr.deliveries.from_folder")}>
              <option value="">{t("atr.deliveries.from_folder")}</option>
              {input.files.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
            <button className="px-3 py-2 border rounded" disabled={!picked || busy}
              onClick={onProcess}>{t("atr.deliveries.process")}</button>
          </div>
        )}
      </div>
      <table className="w-full text-sm">
        <thead><tr className="text-left border-b">
          <th className="py-2">{t("atr.deliveries.col.source")}</th>
          <th>{t("atr.deliveries.col.ba")}</th>
          <th>{t("atr.deliveries.col.status")}</th>
          <th>{t("atr.deliveries.col.created")}</th><th /></tr></thead>
        <tbody>
          {(deliveries ?? []).map((d) => (
            <tr key={d.id} className="border-b" data-testid={`atr-delivery-${d.id}`}>
              <td className="py-1">{d.source_filename}</td>
              <td>{d.ba_auftrag}</td>
              <td>{d.status}</td>
              <td>{new Date(d.created_at).toLocaleString()}</td>
              <td><button className="text-blue-600"
                onClick={() => setLocation(`/atr/deliveries/${d.id}`)}>{t("atr.deliveries.open")}</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Wire the route**

In `frontend/src/App.tsx`: `import { AtrDeliveriesPage } from "./pages/AtrDeliveriesPage";` and add, BEFORE the `<Route path="/atr">` line:
```tsx
<Route path="/atr/deliveries"><AdminOnly><AtrDeliveriesPage /></AdminOnly></Route>
```
(The `/atr/deliveries/:id` review route is added in Task 13, also before `/atr`.)

- [ ] **Step 3: Write the test**

```tsx
// frontend/src/pages/__tests__/AtrDeliveriesPage.test.tsx
import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { describe, it, expect, vi, beforeEach } from "vitest";
import i18n from "@/i18n";
import { AtrDeliveriesPage } from "../AtrDeliveriesPage";
import * as atrApi from "@/lib/atrApi";

vi.mock("@/lib/atrApi");

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const mem = memoryLocation({ path: "/atr/deliveries" });
  return (
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}><Router hook={mem.hook}>{ui}</Router></I18nextProvider>
    </QueryClientProvider>
  );
}

describe("AtrDeliveriesPage", () => {
  beforeEach(() => vi.resetAllMocks());
  it("lists deliveries", async () => {
    vi.mocked(atrApi.fetchInputFiles).mockResolvedValue({ configured: false, files: [] });
    vi.mocked(atrApi.fetchDeliveries).mockResolvedValue([{
      id: 7, source_filename: "LS.pdf", ba_auftrag: "1024738",
      compartment: "CCRC", status: "draft", created_at: "2026-06-25T10:00:00Z",
    }]);
    render(wrap(<AtrDeliveriesPage />));
    await waitFor(() => expect(screen.getByTestId("atr-delivery-7")).toBeInTheDocument());
    expect(screen.getByText("LS.pdf")).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Run the test**

Run: `cd frontend && npx vitest run src/pages/__tests__/AtrDeliveriesPage.test.tsx`
Expected: PASS. Then `cd frontend && npx tsc --noEmit` → clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/AtrDeliveriesPage.tsx frontend/src/App.tsx frontend/src/pages/__tests__/AtrDeliveriesPage.test.tsx
git commit -m "feat(atr): deliveries list page (upload + input-folder)"
```

---

## Task 13: Delivery review page

**Files:**
- Create: `frontend/src/pages/AtrDeliveryReviewPage.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/pages/__tests__/AtrDeliveryReviewPage.test.tsx`

**Interfaces:**
- Consumes: `fetchDelivery`, `updateDelivery`, `updateDeliveryItem`, `generateDelivery`, `atrFileUrl`.

- [ ] **Step 1: Write the page**

```tsx
// frontend/src/pages/AtrDeliveryReviewPage.tsx
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRoute } from "wouter";
import { toast } from "sonner";
import {
  fetchDelivery, updateDelivery, updateDeliveryItem, generateDelivery,
  atrFileUrl, type AtrDelivery,
} from "@/lib/atrApi";

const HEADER_FIELDS: (keyof AtrDelivery)[] = [
  "atr_number", "container_number", "set_title", "po_number",
  "weighing_date", "testing_date", "qa_signer", "max_guaranteed_weight_kg",
];

export function AtrDeliveryReviewPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [, params] = useRoute("/atr/deliveries/:id");
  const id = Number(params?.id);
  const { data } = useQuery({ queryKey: ["atr", "delivery", id], queryFn: () => fetchDelivery(id), enabled: !!id });
  const [draft, setDraft] = useState<Partial<AtrDelivery>>({});
  const [manifest, setManifest] = useState<string[] | null>(null);
  useEffect(() => { if (data) setDraft(data); }, [data]);

  async function saveHeader() {
    try {
      const body: Record<string, unknown> = {};
      HEADER_FIELDS.forEach((f) => { body[f] = (draft as Record<string, unknown>)[f] ?? null; });
      await updateDelivery(id, body as Partial<AtrDelivery>);
      toast.success(t("atr.deliveries.save"));
      qc.invalidateQueries({ queryKey: ["atr", "delivery", id] });
    } catch (e) { toast.error(String(e)); }
  }
  async function saveItem(iid: number, weight: string, po: string) {
    try {
      await updateDeliveryItem(id, iid, { weight_kg: weight || null, po_pos: po || null });
      qc.invalidateQueries({ queryKey: ["atr", "delivery", id] });
    } catch (e) { toast.error(String(e)); }
  }
  async function onGenerate() {
    try {
      const m = await generateDelivery(id);
      setManifest(m.files);
      m.warnings.forEach((w) => toast.warning(w));
      if (!m.warnings.length) toast.success(t("atr.deliveries.generate"));
    } catch (e) { toast.error(String(e)); }
  }

  if (!data) return <div className="p-6">…</div>;
  return (
    <div className="max-w-5xl mx-auto px-6 py-6">
      <h1 className="text-xl font-semibold mb-4">
        {t("atr.deliveries.review.heading")} — {data.source_filename}
      </h1>
      <div className="grid grid-cols-2 gap-3 mb-6">
        {HEADER_FIELDS.map((f) => (
          <label key={f} className="flex flex-col text-sm">
            <span className="text-muted-foreground">{t(`atr.deliveries.field.${f === "max_guaranteed_weight_kg" ? "max_weight" : f}`)}</span>
            <input className="border rounded px-2 py-1"
              value={(draft[f] as string) ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, [f]: e.target.value }))} />
          </label>
        ))}
      </div>
      <button className="mb-4 px-3 py-1 border rounded" onClick={saveHeader}>{t("atr.deliveries.save")}</button>

      <table className="w-full text-sm mb-6">
        <thead><tr className="text-left border-b">
          <th className="py-2">{t("atr.deliveries.item.part_number")}</th>
          <th>{t("atr.deliveries.item.name")}</th>
          <th>{t("atr.deliveries.item.drawing")}</th>
          <th>{t("atr.deliveries.item.weight")}</th>
          <th>{t("atr.deliveries.item.po_pos")}</th></tr></thead>
        <tbody>
          {data.items.map((it) => (
            <tr key={it.id}
              className={`border-b ${it.match_status !== "matched" ? "bg-red-100" : ""}`}
              data-testid={`atr-item-${it.id}`}>
              <td className="py-1 font-mono">{it.part_number}</td>
              <td>{it.part_name}</td>
              <td>{it.drawing_number_issue}</td>
              <td><input className="border rounded px-1 w-20" defaultValue={it.weight_kg ?? ""}
                onBlur={(e) => saveItem(it.id, e.target.value, it.po_pos ?? "")} /></td>
              <td><input className="border rounded px-1 w-16" defaultValue={it.po_pos ?? ""}
                onBlur={(e) => saveItem(it.id, it.weight_kg ?? "", e.target.value)} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      <button className="px-4 py-2 bg-blue-600 text-white rounded mr-4" onClick={onGenerate}>
        {t("atr.deliveries.generate")}
      </button>
      {manifest && (
        <span className="inline-flex gap-3">
          {manifest.includes("atr_xlsx") && <a className="text-blue-600" href={atrFileUrl(id, "atr_xlsx")}>{t("atr.deliveries.download_xlsx")}</a>}
          {manifest.includes("atr_pdf") && <a className="text-blue-600" href={atrFileUrl(id, "atr_pdf")}>{t("atr.deliveries.download_pdf")}</a>}
          {manifest.includes("label_docx") && <a className="text-blue-600" href={atrFileUrl(id, "label_docx")}>{t("atr.deliveries.download_docx")}</a>}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire the route**

In `frontend/src/App.tsx`: `import { AtrDeliveryReviewPage } from "./pages/AtrDeliveryReviewPage";` and add, BEFORE both `<Route path="/atr/deliveries">` and `<Route path="/atr">` (most specific first):
```tsx
<Route path="/atr/deliveries/:id"><AdminOnly><AtrDeliveryReviewPage /></AdminOnly></Route>
```

- [ ] **Step 3: Write the test**

```tsx
// frontend/src/pages/__tests__/AtrDeliveryReviewPage.test.tsx
import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { describe, it, expect, vi, beforeEach } from "vitest";
import i18n from "@/i18n";
import { AtrDeliveryReviewPage } from "../AtrDeliveryReviewPage";
import * as atrApi from "@/lib/atrApi";

vi.mock("@/lib/atrApi");

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const mem = memoryLocation({ path: "/atr/deliveries/7" });
  return (
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}><Router hook={mem.hook}>{ui}</Router></I18nextProvider>
    </QueryClientProvider>
  );
}

describe("AtrDeliveryReviewPage", () => {
  beforeEach(() => vi.resetAllMocks());
  it("renders header + items, flags unmatched", async () => {
    vi.mocked(atrApi.fetchDelivery).mockResolvedValue({
      id: 7, source_filename: "LS.pdf", lieferschein_nr: "20189798", datum: "2026-06-08",
      ba_auftrag: "1024738", po_number: "4501119979", ac_programme: "A350",
      compartment: "CCRC", msn: "830", bed_config: "6", set_title: "SET 6 BED CCRC",
      atr_number: null, container_number: null, weighing_date: "2026-06-25",
      testing_date: "2026-06-25", qa_signer: "Cordula Kesseler i.A.",
      max_guaranteed_weight_kg: null, status: "draft",
      created_at: "2026-06-25T10:00:00Z", updated_at: "2026-06-25T10:00:00Z",
      items: [
        { id: 1, pos: 1, supplier_article_code: "6060", part_number: "VR11S 1010 016 000",
          part_number_norm: "111010016000", matched_part_id: 5, part_name: "CARPET EMERGENCY EXIT HATCH",
          drawing_number_issue: "VR11S 1010-10/D", category: "CARPET", qty: 1,
          weight_kg: "0.413", po_pos: "050", match_status: "matched", row_order: 1 },
        { id: 2, pos: 2, supplier_article_code: "9999", part_number: "VR11S 9999 999 999",
          part_number_norm: "999999999", matched_part_id: null, part_name: "UNKNOWN",
          drawing_number_issue: null, category: null, qty: 1,
          weight_kg: null, po_pos: null, match_status: "unmatched", row_order: 2 },
      ],
    });
    render(wrap(<AtrDeliveryReviewPage />));
    await waitFor(() => expect(screen.getByTestId("atr-item-1")).toBeInTheDocument());
    expect(screen.getByDisplayValue("SET 6 BED CCRC")).toBeInTheDocument();
    expect(screen.getByTestId("atr-item-2").className).toContain("bg-red-100");
  });
});
```

- [ ] **Step 4: Run the test + full frontend atr suite**

Run:
```bash
cd frontend && npx vitest run src/pages/__tests__/Atr*.test.tsx
cd frontend && npx tsc --noEmit
```
Expected: all PASS, tsc clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/AtrDeliveryReviewPage.tsx frontend/src/App.tsx frontend/src/pages/__tests__/AtrDeliveryReviewPage.test.tsx
git commit -m "feat(atr): delivery review page (edit, generate, download)"
```

---

## Acceptance check (manual, after merge)

With the 12 Phase-A reference workbooks imported and a structural template set: upload the real `LIEFERSCHEIN_10005_20189798.pdf`, review, Generate. Confirm the ATR lists the 8 carpet parts with the expected drawing numbers (`VR11S 1010-27/A`, `-28/A`, `-10/D`, …), a plausible total weight, and the label reads `BA 1024738 / PO 4501119979 / Pos. 050, 300, 340, 350, 360, 390, 400, 410 / A350 Teppiche MSN 830 / Container …`.

## Self-Review

- **Spec coverage:** parser (T2) ✓; matcher + set-title/compartment derivation (T3) ✓; tables + provenance (T1) ✓; schemas (T4); ingest router with both input modes + path-traversal guard (T5) ✓; infra libreoffice-calc + python-docx + ATR_INPUT_DIR (T6) ✓; template-as-frame xlsx with red unmatched + totals (T7) ✓; xlsx→PDF async/serialized (T8) ✓; docx label (T9) ✓; generate+download with PDF-failure tolerance + manifest (T10) ✓; review UI list + review pages + i18n (T11–13) ✓; admin gate (T5) ✓; acceptance check ✓.
- **Placeholder scan:** none — every step has runnable code/commands.
- **Type consistency:** `parse_lieferschein`/`ParsedLieferschein`/`ParsedPosition`, `match_positions`/`MatchedDelivery`/`MatchedItem`, `build_atr_xlsx`/`convert_xlsx_to_pdf`/`build_containerbeschriftung`, `AtrGenerateManifest` fields, and the TS fetcher names are consistent across tasks.
- **Risk flagged:** the openpyxl region delete/insert in T7 is the trickiest part; its test re-opens the produced xlsx and asserts cells + red fill, and the task notes the unmerge/re-merge fallback if LibreOffice flags the file.
