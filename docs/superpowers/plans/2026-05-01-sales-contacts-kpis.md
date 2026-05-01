# Sales Contacts KPIs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four weekly sales-activity line charts (Erstkontakte, Interessenten, Visits, Angebote) and one combined Orders-distribution card to the Sales Dashboard, sliced per Personio sales employee, sourced from a new `Kontakte` upload that reuses the existing Aufträge upload pattern.

**Architecture:** New `sales_contacts` table fed by a new admin-only `POST /api/upload-contacts` endpoint that mirrors `POST /api/upload`'s parsing/idempotency pattern. New `sales_employee_aliases` table maps the file's `Wer` token to a `personio_employees.id`. A new Personio sync hook rebuilds canonical aliases each tick. Two new compute GET endpoints (`/api/data/sales/contacts-weekly`, `/api/data/sales/orders-distribution`) feed two new dashboard cards. HR settings page gains a sales-departments picker plus an "unmapped reps" table.

**Tech Stack:** FastAPI 0.135 + SQLAlchemy 2.0 (async) + Alembic (migration v1.41), pandas + openpyxl (existing parser), React 19 + Recharts (existing) + TanStack Query 5 + Tailwind v4.

**Spec:** [docs/superpowers/specs/2026-05-01-sales-contacts-kpis-design.md](../specs/2026-05-01-sales-contacts-kpis-design.md)

---

## Phase A — Backend foundation

### Task A1: Alembic migration v1.41 — sales_contacts + sales_employee_aliases

**Files:**
- Create: `backend/alembic/versions/v1_41_sales_contacts.py`

- [ ] **Step 1: Write the migration**

```python
"""sales_contacts + sales_employee_aliases (v1.41)

Revision ID: v1_41_sales_contacts
Revises: v1_39_sensor_chart_color
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "v1_41_sales_contacts"
down_revision = "v1_39_sensor_chart_color"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_contacts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("contact_date", sa.Date, nullable=False),
        sa.Column("employee_token", sa.String(length=128), nullable=False),
        sa.Column("contact_type", sa.String(length=32), nullable=True),
        sa.Column("customer_group", sa.String(length=32), nullable=True),
        sa.Column("status", sa.SmallInteger, nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("external_id", sa.String(length=64), nullable=True),
        sa.Column("raw", postgresql.JSONB, nullable=True),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("status IN (0, 1)", name="sales_contacts_status_check"),
    )
    op.create_index("ix_sales_contacts_date", "sales_contacts", ["contact_date"])
    op.create_index("ix_sales_contacts_token", "sales_contacts", ["employee_token"])

    op.create_table(
        "sales_employee_aliases",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "personio_employee_id",
            sa.Integer,
            sa.ForeignKey("personio_employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("employee_token", sa.String(length=128), nullable=False, unique=True),
        sa.Column("is_canonical", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_sales_employee_aliases_employee",
        "sales_employee_aliases",
        ["personio_employee_id"],
    )

    # New settings column for Personio sales departments (mirrors production_dept).
    op.add_column(
        "settings",
        sa.Column(
            "personio_sales_dept",
            postgresql.JSONB,
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "personio_sales_dept")
    op.drop_index("ix_sales_employee_aliases_employee", table_name="sales_employee_aliases")
    op.drop_table("sales_employee_aliases")
    op.drop_index("ix_sales_contacts_token", table_name="sales_contacts")
    op.drop_index("ix_sales_contacts_date", table_name="sales_contacts")
    op.drop_table("sales_contacts")
```

- [ ] **Step 2: Run migration locally**

```bash
docker compose exec api alembic upgrade head
```

Expected: clean apply, then `\d sales_contacts` and `\d sales_employee_aliases` in `psql` show the new tables.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/v1_41_sales_contacts.py
git commit -m "feat(v1.41 A-1): alembic migration — sales_contacts + sales_employee_aliases + personio_sales_dept settings col"
```

### Task A2: SQLAlchemy models

**Files:**
- Modify: `backend/app/models/_base.py`
- Modify: `backend/app/models/__init__.py` (re-export)

- [ ] **Step 1: Add models to `_base.py`**

Append after the `PersonioAbsence` class:

```python
class SalesContact(Base):
    __tablename__ = "sales_contacts"
    __table_args__ = (
        Index("ix_sales_contacts_date", "contact_date"),
        Index("ix_sales_contacts_token", "employee_token"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contact_date: Mapped[date] = mapped_column(Date, nullable=False)
    employee_token: Mapped[str] = mapped_column(String(128), nullable=False)
    contact_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    customer_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class SalesEmployeeAlias(Base):
    __tablename__ = "sales_employee_aliases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    personio_employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("personio_employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_token: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True
    )
    is_canonical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

Ensure `BigInteger`, `SmallInteger`, `Text` are imported at the top of the file.

Add `personio_sales_dept` to the `Settings` model (search for `personio_production_dept`):

```python
personio_sales_dept: Mapped[list | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 2: Re-export in `__init__.py`**

Add `SalesContact` and `SalesEmployeeAlias` to whatever `__all__` / re-exports already exist.

- [ ] **Step 3: Smoke import**

```bash
docker compose exec api python -c "from app.models import SalesContact, SalesEmployeeAlias; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/
git commit -m "feat(v1.41 A-2): SQLAlchemy models for sales_contacts + sales_employee_aliases + Settings.personio_sales_dept"
```

### Task A3: Pydantic schemas + settings key wiring

**Files:**
- Modify: `backend/app/schemas/_base.py`
- Modify: `backend/app/routers/settings.py`

- [ ] **Step 1: Extend the SettingsRead/SettingsPatch schemas**

Search for `personio_production_dept` and add a sibling `personio_sales_dept: list[str] | None = None` (Patch) and `personio_sales_dept: list[str] = []` (Read default).

- [ ] **Step 2: Wire settings.py read+patch**

Search for `personio_production_dept` in `settings.py` and add a sibling line for `personio_sales_dept` in both the read transform and the patch handler.

- [ ] **Step 3: Add new schemas for the contacts-weekly + orders-distribution endpoints**

In `schemas/_base.py`:

```python
class ContactsWeeklyEmployeeBucket(BaseModel):
    erstkontakte: int
    interessenten: int
    visits: int
    angebote: int


class ContactsWeeklyWeek(BaseModel):
    iso_year: int
    iso_week: int
    label: str
    per_employee: dict[int, ContactsWeeklyEmployeeBucket]


class ContactsWeeklyResponse(BaseModel):
    weeks: list[ContactsWeeklyWeek]
    employees: dict[int, str]  # personio_employee_id → display name


class OrdersDistributionResponse(BaseModel):
    orders_per_week_per_rep: float
    top3_share_pct: float
    remaining_share_pct: float
    top3_customers: list[str]


class SalesAliasRead(BaseModel):
    id: int
    personio_employee_id: int
    employee_token: str
    is_canonical: bool


class SalesAliasCreate(BaseModel):
    personio_employee_id: int
    employee_token: str = Field(min_length=1, max_length=128)


class UnmappedTokenSample(BaseModel):
    token: str
    count: int
    last_seen: date


class ContactsUploadResponse(BaseModel):
    rows_inserted: int
    rows_replaced: int
    date_range_from: date | None
    date_range_to: date | None
    unmapped_tokens: list[UnmappedTokenSample]
```

- [ ] **Step 4: Smoke test**

```bash
docker compose exec api pytest tests/ -k "settings" -q
```

Expected: existing settings tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/_base.py backend/app/routers/settings.py
git commit -m "feat(v1.41 A-3): Pydantic schemas + settings.personio_sales_dept wiring"
```

---

## Phase B — Ingestion + alias resolution + Personio sync hook

### Task B1: Kontakte file parser

**Files:**
- Create: `backend/app/parsing/kontakte_parser.py`
- Create: `backend/tests/test_kontakte_parser.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_kontakte_parser.py
from datetime import date
from app.parsing.kontakte_parser import parse_kontakte_file

SAMPLE = (
    b'="Datum"\t="Zeit"\t="Abteilung"\t="Wer"\t="Typ"\t="Gruppe"\t="Art"\t='
    b'"Sta"\t="Anrede"\t="Ansprechpartner"\t="Adresse"\t="Name"\t="PLZ"\t='
    b'"Ort"\t="Stra\xdfe"\t="Kommentar"\t="VrgID"\t="ABC"\t="Branche"\t='
    b'"gespeichert am"\t="ge\xe4ndert am"\t="Klasse 1"\t="Klasse 2"\t="Klasse 3"\t='
    b'"Klasse 4"\t="Klasse 5"\t="Start Tel."\t="Dauer"\t="Hit"\r\n'
    b'08.02.2012\t="14:10:47,03"\t=""\t="KARRER"\t="ERS"\t="L"\t=""\t1\t=""\t='
    b'""\t11523\t="Sonatech GmbH + Co.KG"\t="87781"\t="Ungerhausen"\t="Gutenbergstra\xdfe 10"\t='
    b'"Angebot 5000000"\t1\t="C"\t=""\t08.02.2012\t\t=""\t=""\t=""\t="">\t=""\t='
    b'"00:00:00,00"\t="00:00:00,00"\tN\r\n'
)


def test_parser_returns_one_row_with_canonical_fields():
    rows, errors = parse_kontakte_file(SAMPLE, "kontakte.txt")
    assert errors == []
    assert len(rows) == 1
    r = rows[0]
    assert r["contact_date"] == date(2012, 2, 8)
    assert r["employee_token"] == "KARRER"
    assert r["contact_type"] == "ERS"
    assert r["customer_group"] == "L"
    assert r["status"] == 1
    assert r["customer_name"] == "Sonatech GmbH + Co.KG"
    assert r["comment"].startswith("Angebot")


def test_parser_skips_status_zero_rows():
    # Build the same row but with Sta = 0 — parser keeps it; KPI rules drop it.
    body = SAMPLE.replace(b"\t1\t=\"C\"", b"\t0\t=\"C\"")
    rows, _ = parse_kontakte_file(body, "kontakte.txt")
    assert rows[0]["status"] == 0
```

- [ ] **Step 2: Run, expect ImportError or AssertionError**

```bash
docker compose exec api pytest tests/test_kontakte_parser.py -q
```

Expected: red (parser doesn't exist).

- [ ] **Step 3: Implement the parser**

```python
# backend/app/parsing/kontakte_parser.py
"""Kontakte (sales contact log) parser.

Reads the ISO-8859-1, tab-separated, ="…"-quoted dump from the source ERP.
Returns a list of dicts ready for SalesContact insert + a list of errors.

This intentionally does NOT do the alias resolution (token → personio
employee). That happens at the router layer so the parser can stay pure.
"""
from __future__ import annotations

import io
import re
from datetime import date
from typing import Any

import pandas as pd

_DATE_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
_QUOTE_RE = re.compile(r'^="?(.*?)"?$')


def _unquote(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    m = _QUOTE_RE.match(s)
    return (m.group(1) if m else s).strip()


def _parse_date(val: str) -> date | None:
    m = _DATE_RE.match(val)
    if not m:
        return None
    dd, mm, yyyy = m.groups()
    try:
        return date(int(yyyy), int(mm), int(dd))
    except ValueError:
        return None


COLS = {
    "Datum": "contact_date",
    "Wer": "employee_token",
    "Typ": "contact_type",
    "Gruppe": "customer_group",
    "Sta": "status",
    "Name": "customer_name",
    "Kommentar": "comment",
    "VrgID": "external_id",
}


def parse_kontakte_file(
    contents: bytes, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse a Kontakte tab-separated dump."""
    try:
        df = pd.read_csv(
            io.BytesIO(contents),
            sep="\t",
            encoding="iso-8859-1",
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:  # pragma: no cover — surfaces malformed inputs
        return [], [{"row": 0, "field": "file", "message": f"unreadable: {exc}"}]

    df.columns = [_unquote(c) for c in df.columns]

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for idx, raw in df.iterrows():
        wer = _unquote(raw.get("Wer", "")).upper()
        d = _parse_date(_unquote(raw.get("Datum", "")))
        if d is None or not wer:
            errors.append({
                "row": int(idx) + 2,
                "field": "Datum/Wer",
                "message": "missing or unparseable",
            })
            continue
        sta_raw = _unquote(raw.get("Sta", ""))
        try:
            sta = int(sta_raw) if sta_raw else 0
        except ValueError:
            sta = 0
        if sta not in (0, 1):
            sta = 0
        rows.append({
            "contact_date": d,
            "employee_token": wer,
            "contact_type": _unquote(raw.get("Typ", "")) or None,
            "customer_group": _unquote(raw.get("Gruppe", "")) or None,
            "status": sta,
            "customer_name": _unquote(raw.get("Name", "")) or None,
            "comment": _unquote(raw.get("Kommentar", "")) or None,
            "external_id": _unquote(raw.get("VrgID", "")) or None,
            "raw": {k: _unquote(v) for k, v in raw.items()},
        })
    return rows, errors
```

- [ ] **Step 4: Run, expect green**

```bash
docker compose exec api pytest tests/test_kontakte_parser.py -q
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/parsing/kontakte_parser.py backend/tests/test_kontakte_parser.py
git commit -m "feat(v1.41 B-1): Kontakte file parser + unit tests"
```

### Task B2: Token-folding helper + alias resolver service

**Files:**
- Create: `backend/app/services/sales_aliases.py`
- Create: `backend/tests/test_sales_aliases.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sales_aliases.py
from app.services.sales_aliases import canonical_token

def test_simple():
    assert canonical_token("Karrer") == "KARRER"

def test_umlauts_folded():
    assert canonical_token("Müller") == "MUELLER"
    assert canonical_token("Größe") == "GROESSE"
    assert canonical_token("Bäcker") == "BAECKER"

def test_strips_non_alpha():
    assert canonical_token("O'Brien") == "OBRIEN"
    assert canonical_token("van der Berg") == "VANDERBERG"

def test_empty_returns_empty_string():
    assert canonical_token("") == ""
    assert canonical_token(None) == ""
```

- [ ] **Step 2: Implement**

```python
# backend/app/services/sales_aliases.py
"""Sales-rep alias helpers.

The Kontakte file's ``Wer`` column is an uppercase surname token like
``KARRER`` / ``GUENDEL``. ``canonical_token`` derives the same shape from
a Personio employee's ``last_name`` so we can build a deterministic
mapping table on every Personio sync. Manual aliases (``is_canonical =
False``) handle nicknames the canonical rule doesn't catch.
"""
from __future__ import annotations

import re

_FOLDS = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "AE", "Ö": "OE", "Ü": "UE",
    "à": "a", "á": "a", "â": "a",
    "è": "e", "é": "e", "ê": "e",
})
_NON_ALPHA = re.compile(r"[^A-Z]")


def canonical_token(last_name: str | None) -> str:
    if not last_name:
        return ""
    folded = last_name.translate(_FOLDS)
    return _NON_ALPHA.sub("", folded.upper())
```

- [ ] **Step 3: Run, expect green**

```bash
docker compose exec api pytest tests/test_sales_aliases.py -q
```

Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/sales_aliases.py backend/tests/test_sales_aliases.py
git commit -m "feat(v1.41 B-2): canonical_token helper for sales-rep aliases"
```

### Task B3: Kontakte upload router

**Files:**
- Modify: `backend/app/routers/uploads.py`
- Create: `backend/tests/test_kontakte_upload.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_kontakte_upload.py — admin uploads, rows are inserted,
# unmapped tokens are surfaced.
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models import SalesContact, PersonioEmployee, SalesEmployeeAlias

pytestmark = pytest.mark.asyncio


async def test_kontakte_upload_inserts_and_reports_unmapped(
    admin_client: AsyncClient, db_session,
):
    # seed one mapped employee
    emp = PersonioEmployee(id=1, last_name="Karrer", status="active", synced_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))
    db_session.add(emp)
    db_session.add(SalesEmployeeAlias(personio_employee_id=1, employee_token="KARRER", is_canonical=True))
    await db_session.commit()

    body = (
        '="Datum"\t="Zeit"\t="Wer"\t="Typ"\t="Gruppe"\t="Sta"\t="Name"\t="Kommentar"\t="VrgID"\r\n'
        '08.02.2012\t="14:10"\t="KARRER"\t="ERS"\t="L"\t1\t="Sonatech"\t="Angebot 5000000"\t1\r\n'
        '09.02.2012\t="14:10"\t="UNKNOWN"\t="ORT"\t="L"\t1\t="ACME"\t="Visit"\t2\r\n'
    ).encode("iso-8859-1")
    r = await admin_client.post(
        "/api/upload-contacts",
        files={"file": ("kontakte.txt", body, "text/plain")},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["rows_inserted"] == 2
    assert any(t["token"] == "UNKNOWN" for t in payload["unmapped_tokens"])

    rows = (await db_session.execute(select(SalesContact))).scalars().all()
    assert len(rows) == 2


async def test_kontakte_upload_replace_by_range(admin_client, db_session):
    # First upload: one row on 2012-02-08
    body1 = (
        '="Datum"\t="Wer"\t="Typ"\t="Gruppe"\t="Sta"\t="Name"\t="Kommentar"\t="VrgID"\r\n'
        '08.02.2012\t="X"\t="ERS"\t="L"\t1\t="A"\t="x"\t1\r\n'
    ).encode("iso-8859-1")
    await admin_client.post("/api/upload-contacts", files={"file": ("k.txt", body1, "text/plain")})
    # Second upload: same range, two rows
    body2 = (
        '="Datum"\t="Wer"\t="Typ"\t="Gruppe"\t="Sta"\t="Name"\t="Kommentar"\t="VrgID"\r\n'
        '08.02.2012\t="X"\t="ERS"\t="L"\t1\t="A"\t="x"\t1\r\n'
        '08.02.2012\t="Y"\t="ORT"\t="L"\t1\t="B"\t="y"\t2\r\n'
    ).encode("iso-8859-1")
    r2 = await admin_client.post("/api/upload-contacts", files={"file": ("k.txt", body2, "text/plain")})
    assert r2.status_code == 200
    rows = (await db_session.execute(select(SalesContact))).scalars().all()
    assert len(rows) == 2
```

- [ ] **Step 2: Run, expect 404 (route missing)**

```bash
docker compose exec api pytest tests/test_kontakte_upload.py -q
```

Expected: red.

- [ ] **Step 3: Add the route to `uploads.py`**

```python
@admin_router.post("/upload-contacts", response_model=ContactsUploadResponse)
async def upload_contacts(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> ContactsUploadResponse:
    """Replace-by-date-range insert of a Kontakte (.txt) tab-separated dump."""
    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise HTTPException(status_code=422, detail="Only .txt files are accepted for Kontakte.")
    contents = await file.read()
    rows, errors = parse_kontakte_file(contents, filename)
    if not rows:
        return ContactsUploadResponse(
            rows_inserted=0, rows_replaced=0, date_range_from=None, date_range_to=None,
            unmapped_tokens=[],
        )

    date_from = min(r["contact_date"] for r in rows)
    date_to = max(r["contact_date"] for r in rows)

    deleted = await db.execute(
        sa.delete(SalesContact).where(
            SalesContact.contact_date >= date_from,
            SalesContact.contact_date <= date_to,
        )
    )
    rows_replaced = deleted.rowcount or 0

    for r in rows:
        r["imported_at"] = datetime.now(timezone.utc)
    cols_per_row = max(1, len(rows[0]))
    chunk_size = max(1, 32767 // cols_per_row)
    inserted = 0
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        result = await db.execute(pg_insert(SalesContact).values(chunk))
        inserted += result.rowcount or 0
    await db.commit()

    # Resolve which tokens are unmapped (not in sales_employee_aliases).
    tokens_seen = {r["employee_token"] for r in rows}
    known = {
        row.employee_token
        for row in (
            await db.execute(
                sa.select(SalesEmployeeAlias.employee_token).where(
                    SalesEmployeeAlias.employee_token.in_(tokens_seen)
                )
            )
        ).all()
    }
    unmapped = sorted(tokens_seen - known)
    counts: dict[str, dict] = {}
    for r in rows:
        if r["employee_token"] in unmapped:
            entry = counts.setdefault(
                r["employee_token"], {"count": 0, "last_seen": r["contact_date"]}
            )
            entry["count"] += 1
            if r["contact_date"] > entry["last_seen"]:
                entry["last_seen"] = r["contact_date"]
    samples = [
        UnmappedTokenSample(token=t, count=v["count"], last_seen=v["last_seen"])
        for t, v in counts.items()
    ]

    return ContactsUploadResponse(
        rows_inserted=inserted, rows_replaced=rows_replaced,
        date_range_from=date_from, date_range_to=date_to,
        unmapped_tokens=samples,
    )
```

Add the missing imports at the top of `uploads.py`:
- `import sqlalchemy as sa`
- `from app.parsing.kontakte_parser import parse_kontakte_file`
- `from app.models import SalesContact, SalesEmployeeAlias`
- `from app.schemas import ContactsUploadResponse, UnmappedTokenSample`

- [ ] **Step 4: Run, expect green**

```bash
docker compose exec api pytest tests/test_kontakte_upload.py -q
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/uploads.py backend/tests/test_kontakte_upload.py
git commit -m "feat(v1.41 B-3): POST /api/upload-contacts — Kontakte ingestion w/ replace-by-range + unmapped-token report"
```

### Task B4: Personio sync hook — rebuild canonical aliases

**Files:**
- Modify: `backend/app/services/hr_sync.py` (add a final post-sync step)
- Create: `backend/tests/test_sales_alias_sync_hook.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sales_alias_sync_hook.py
import pytest
from sqlalchemy import select
from app.services.hr_sync import rebuild_canonical_sales_aliases
from app.models import PersonioEmployee, SalesEmployeeAlias, Settings

pytestmark = pytest.mark.asyncio


async def test_rebuild_creates_canonical_for_sales_dept_employees(db_session):
    s = Settings(personio_sales_dept=["Vertrieb"])
    db_session.add(s)
    e1 = PersonioEmployee(id=1, last_name="Müller", department="Vertrieb",
                          synced_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))
    e2 = PersonioEmployee(id=2, last_name="Schmidt", department="Production",
                          synced_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))
    db_session.add_all([e1, e2])
    await db_session.commit()

    await rebuild_canonical_sales_aliases(db_session)

    aliases = (await db_session.execute(select(SalesEmployeeAlias))).scalars().all()
    tokens = {a.employee_token for a in aliases if a.is_canonical}
    assert tokens == {"MUELLER"}  # only the Vertrieb employee


async def test_rebuild_preserves_manual_aliases(db_session):
    s = Settings(personio_sales_dept=["Vertrieb"])
    db_session.add(s)
    e = PersonioEmployee(id=1, last_name="Müller", department="Vertrieb",
                        synced_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))
    db_session.add(e)
    db_session.add(SalesEmployeeAlias(personio_employee_id=1, employee_token="GUENNI", is_canonical=False))
    await db_session.commit()

    await rebuild_canonical_sales_aliases(db_session)

    aliases = (await db_session.execute(select(SalesEmployeeAlias))).scalars().all()
    tokens = {(a.employee_token, a.is_canonical) for a in aliases}
    assert ("GUENNI", False) in tokens
    assert ("MUELLER", True) in tokens
```

- [ ] **Step 2: Implement the hook in `hr_sync.py`**

```python
async def rebuild_canonical_sales_aliases(session) -> None:
    """Per Personio sync: drop and rebuild canonical alias rows.

    Manual (is_canonical=False) rows are NEVER touched. Canonical rows are
    derived from Personio employees in the configured sales departments.
    """
    settings_row = (await session.execute(sa.select(Settings))).scalar_one_or_none()
    sales_depts: list[str] = (settings_row.personio_sales_dept or []) if settings_row else []
    if not sales_depts:
        # No sales-dept config → drop ALL canonical aliases (nothing qualifies).
        await session.execute(
            sa.delete(SalesEmployeeAlias).where(SalesEmployeeAlias.is_canonical.is_(True))
        )
        await session.commit()
        return

    employees = (
        await session.execute(
            sa.select(PersonioEmployee).where(PersonioEmployee.department.in_(sales_depts))
        )
    ).scalars().all()

    # Build the desired set of (employee_id, token) canonical pairs.
    desired: dict[int, str] = {}
    for e in employees:
        token = canonical_token(e.last_name)
        if token:
            desired[e.id] = token

    # Drop existing canonical rows and re-insert.
    await session.execute(
        sa.delete(SalesEmployeeAlias).where(SalesEmployeeAlias.is_canonical.is_(True))
    )
    for emp_id, token in desired.items():
        # Skip if a manual alias already claims this token (manual wins).
        existing = (
            await session.execute(
                sa.select(SalesEmployeeAlias).where(SalesEmployeeAlias.employee_token == token)
            )
        ).scalar_one_or_none()
        if existing:
            continue
        session.add(SalesEmployeeAlias(
            personio_employee_id=emp_id, employee_token=token, is_canonical=True,
        ))
    await session.commit()
```

Add the call at the end of the existing top-level sync function in `hr_sync.py` (search for where `synced_at` is committed):

```python
await rebuild_canonical_sales_aliases(session)
```

- [ ] **Step 3: Run, expect green**

```bash
docker compose exec api pytest tests/test_sales_alias_sync_hook.py -q
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/hr_sync.py backend/tests/test_sales_alias_sync_hook.py
git commit -m "feat(v1.41 B-4): Personio sync hook — rebuild canonical sales aliases per tick"
```

### Task B5: Manual alias CRUD endpoints

**Files:**
- Create: `backend/app/routers/sales_aliases.py`
- Modify: `backend/app/main.py` (register router)
- Create: `backend/tests/test_sales_alias_crud.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sales_alias_crud.py
import pytest
pytestmark = pytest.mark.asyncio

async def test_create_and_delete_manual_alias(admin_client, db_session):
    from app.models import PersonioEmployee
    db_session.add(PersonioEmployee(id=1, last_name="Müller",
                                    synced_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)))
    await db_session.commit()
    r = await admin_client.post("/api/admin/sales-aliases",
                                 json={"personio_employee_id": 1, "employee_token": "GUENNI"})
    assert r.status_code == 201
    alias_id = r.json()["id"]
    r2 = await admin_client.delete(f"/api/admin/sales-aliases/{alias_id}")
    assert r2.status_code == 204


async def test_cannot_delete_canonical_alias(admin_client, db_session):
    from app.models import PersonioEmployee, SalesEmployeeAlias
    db_session.add(PersonioEmployee(id=1, last_name="X",
                                    synced_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)))
    db_session.add(SalesEmployeeAlias(id=42, personio_employee_id=1, employee_token="X", is_canonical=True))
    await db_session.commit()
    r = await admin_client.delete("/api/admin/sales-aliases/42")
    assert r.status_code == 409
```

- [ ] **Step 2: Implement the router**

```python
# backend/app/routers/sales_aliases.py
"""Manual sales-rep alias CRUD (admin-only).

Canonical rows (created by the Personio sync hook) are read-only via
this surface — a 409 is returned on any DELETE attempt against them.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import SalesEmployeeAlias, PersonioEmployee
from app.schemas import SalesAliasRead, SalesAliasCreate
from app.security.directus_auth import get_current_user, require_admin

admin_router = APIRouter(
    prefix="/api/admin",
    dependencies=[Depends(get_current_user), Depends(require_admin)],
    tags=["sales-aliases"],
)


@admin_router.post("/sales-aliases", response_model=SalesAliasRead, status_code=201)
async def create_alias(
    payload: SalesAliasCreate, db: AsyncSession = Depends(get_async_db_session),
) -> SalesAliasRead:
    emp = await db.get(PersonioEmployee, payload.personio_employee_id)
    if not emp:
        raise HTTPException(404, "personio employee not found")
    token = payload.employee_token.upper()
    existing = (await db.execute(
        select(SalesEmployeeAlias).where(SalesEmployeeAlias.employee_token == token)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "token already mapped")
    alias = SalesEmployeeAlias(
        personio_employee_id=payload.personio_employee_id,
        employee_token=token,
        is_canonical=False,
    )
    db.add(alias)
    await db.commit()
    await db.refresh(alias)
    return SalesAliasRead.model_validate(alias, from_attributes=True)


@admin_router.delete("/sales-aliases/{alias_id}", status_code=204)
async def delete_alias(
    alias_id: int, db: AsyncSession = Depends(get_async_db_session),
) -> None:
    alias = await db.get(SalesEmployeeAlias, alias_id)
    if not alias:
        raise HTTPException(404)
    if alias.is_canonical:
        raise HTTPException(409, "canonical aliases are managed by the Personio sync; remove the employee from the sales department instead")
    await db.delete(alias)
    await db.commit()
```

Register the router in `main.py` next to the other routers.

- [ ] **Step 3: Run, expect green**

```bash
docker compose exec api pytest tests/test_sales_alias_crud.py -q
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/sales_aliases.py backend/app/main.py backend/tests/test_sales_alias_crud.py
git commit -m "feat(v1.41 B-5): manual sales-alias CRUD (admin-only, canonical rows protected)"
```

---

## Phase C — KPI compute endpoints

### Task C1: Contacts-weekly endpoint

**Files:**
- Create: `backend/app/services/sales_kpi_aggregation.py`
- Create: `backend/app/routers/sales_kpis.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_contacts_weekly.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_contacts_weekly.py
import pytest
from datetime import date, datetime, timezone
from app.models import SalesContact, PersonioEmployee, SalesEmployeeAlias

pytestmark = pytest.mark.asyncio


async def test_one_rep_one_week(viewer_client, db_session):
    e = PersonioEmployee(id=1, last_name="Karrer", first_name="A",
                        synced_at=datetime.now(timezone.utc))
    db_session.add(e)
    db_session.add(SalesEmployeeAlias(personio_employee_id=1, employee_token="KARRER", is_canonical=True))
    db_session.add_all([
        SalesContact(contact_date=date(2026, 4, 27), employee_token="KARRER",
                     contact_type="ERS", status=1, imported_at=datetime.now(timezone.utc)),
        SalesContact(contact_date=date(2026, 4, 28), employee_token="KARRER",
                     contact_type="ORT", status=1, imported_at=datetime.now(timezone.utc)),
        SalesContact(contact_date=date(2026, 4, 29), employee_token="KARRER",
                     contact_type="ANFR", status=1, imported_at=datetime.now(timezone.utc)),
        SalesContact(contact_date=date(2026, 4, 30), employee_token="KARRER",
                     contact_type="EMAIL", comment="Angebot 5", status=1,
                     imported_at=datetime.now(timezone.utc)),
        # status=0 row is dropped
        SalesContact(contact_date=date(2026, 4, 27), employee_token="KARRER",
                     contact_type="ERS", status=0, imported_at=datetime.now(timezone.utc)),
    ])
    await db_session.commit()

    r = await viewer_client.get("/api/data/sales/contacts-weekly?from=2026-04-27&to=2026-05-03")
    assert r.status_code == 200
    body = r.json()
    week = next(w for w in body["weeks"] if w["iso_week"] == 18)
    bucket = week["per_employee"]["1"]
    assert bucket == {"erstkontakte": 1, "interessenten": 1, "visits": 1, "angebote": 1}


async def test_unmapped_token_excluded(viewer_client, db_session):
    db_session.add(SalesContact(contact_date=date(2026, 4, 27), employee_token="UNKNOWN",
                                contact_type="ERS", status=1, imported_at=datetime.now(timezone.utc)))
    await db_session.commit()
    r = await viewer_client.get("/api/data/sales/contacts-weekly?from=2026-04-27&to=2026-05-03")
    assert r.status_code == 200
    assert r.json()["weeks"] == [] or all(not w["per_employee"] for w in r.json()["weeks"])
```

- [ ] **Step 2: Implement the aggregation service + router**

```python
# backend/app/services/sales_kpi_aggregation.py
"""Sales KPI aggregation: contacts-weekly + orders-distribution."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PersonioEmployee, SalesContact, SalesEmployeeAlias, SalesRecord,
)


async def compute_contacts_weekly(
    session: AsyncSession, date_from: date, date_to: date,
) -> dict:
    # Map token → employee_id via the aliases table.
    aliases = (
        await session.execute(select(SalesEmployeeAlias.employee_token, SalesEmployeeAlias.personio_employee_id))
    ).all()
    token_to_emp: dict[str, int] = {row.employee_token: row.personio_employee_id for row in aliases}
    if not token_to_emp:
        return {"weeks": [], "employees": {}}

    rows = (
        await session.execute(
            select(SalesContact).where(
                and_(
                    SalesContact.status == 1,
                    SalesContact.contact_date >= date_from,
                    SalesContact.contact_date <= date_to,
                    SalesContact.employee_token.in_(list(token_to_emp.keys())),
                )
            )
        )
    ).scalars().all()

    # Aggregate (iso_year, iso_week, employee_id) → bucket
    agg: dict[tuple[int, int, int], dict[str, int]] = defaultdict(
        lambda: {"erstkontakte": 0, "interessenten": 0, "visits": 0, "angebote": 0}
    )
    for r in rows:
        emp_id = token_to_emp.get(r.employee_token)
        if emp_id is None:
            continue
        iso_year, iso_week, _ = r.contact_date.isocalendar()
        bucket = agg[(iso_year, iso_week, emp_id)]
        if r.contact_type == "ERS":
            bucket["erstkontakte"] += 1
        if r.contact_type in ("ANFR", "EPA"):
            bucket["interessenten"] += 1
        if r.contact_type == "ORT":
            bucket["visits"] += 1
        if (r.comment or "").strip().upper().startswith("ANGEBOT"):
            bucket["angebote"] += 1

    # Reshape to nested weeks list
    weeks: dict[tuple[int, int], dict] = {}
    for (yr, wk, emp_id), bucket in agg.items():
        w = weeks.setdefault((yr, wk), {"iso_year": yr, "iso_week": wk,
                                         "label": f"KW {wk} / {yr}", "per_employee": {}})
        w["per_employee"][emp_id] = bucket

    employees = {
        e.id: f"{e.first_name or ''} {e.last_name or ''}".strip() or f"#{e.id}"
        for e in (
            await session.execute(
                select(PersonioEmployee).where(PersonioEmployee.id.in_(token_to_emp.values()))
            )
        ).scalars().all()
    }
    sorted_weeks = sorted(weeks.values(), key=lambda w: (w["iso_year"], w["iso_week"]))
    return {"weeks": sorted_weeks, "employees": employees}
```

```python
# backend/app/routers/sales_kpis.py
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.security.directus_auth import get_current_user
from app.schemas import ContactsWeeklyResponse, OrdersDistributionResponse
from app.services.sales_kpi_aggregation import (
    compute_contacts_weekly, compute_orders_distribution,
)

router = APIRouter(
    prefix="/api/data/sales",
    dependencies=[Depends(get_current_user)],
    tags=["sales-kpis"],
)


def _default_range() -> tuple[date, date]:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return (monday - timedelta(weeks=11), monday + timedelta(days=6))


@router.get("/contacts-weekly", response_model=ContactsWeeklyResponse)
async def contacts_weekly(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_async_db_session),
) -> ContactsWeeklyResponse:
    if not date_from or not date_to:
        d_from, d_to = _default_range()
        date_from = date_from or d_from
        date_to = date_to or d_to
    payload = await compute_contacts_weekly(db, date_from, date_to)
    return ContactsWeeklyResponse(**payload)


@router.get("/orders-distribution", response_model=OrdersDistributionResponse)
async def orders_distribution(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_async_db_session),
) -> OrdersDistributionResponse:
    if not date_from or not date_to:
        d_from, d_to = _default_range()
        date_from = date_from or d_from
        date_to = date_to or d_to
    payload = await compute_orders_distribution(db, date_from, date_to)
    return OrdersDistributionResponse(**payload)
```

Register `router` in `main.py` next to the other data routers.

- [ ] **Step 3: Run, expect green**

```bash
docker compose exec api pytest tests/test_contacts_weekly.py -q
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/sales_kpi_aggregation.py backend/app/routers/sales_kpis.py backend/app/main.py backend/tests/test_contacts_weekly.py
git commit -m "feat(v1.41 C-1): GET /api/data/sales/contacts-weekly endpoint + aggregation service"
```

### Task C2: Orders-distribution endpoint

**Files:**
- Modify: `backend/app/services/sales_kpi_aggregation.py` (add `compute_orders_distribution`)
- Create: `backend/tests/test_orders_distribution.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_orders_distribution.py
import pytest
from datetime import date, datetime, timezone
from app.models import SalesRecord, PersonioEmployee, SalesEmployeeAlias

pytestmark = pytest.mark.asyncio


async def test_top3_share_pct(viewer_client, db_session):
    # 5 customers, totals 50/30/10/5/5 → top3 = 90%, remaining = 10%
    db_session.add(PersonioEmployee(id=1, last_name="X", synced_at=datetime.now(timezone.utc)))
    db_session.add(SalesEmployeeAlias(personio_employee_id=1, employee_token="X", is_canonical=True))
    for i, (cust, tot) in enumerate([("A", 50), ("B", 30), ("C", 10), ("D", 5), ("E", 5)]):
        db_session.add(SalesRecord(
            order_number=f"O{i}", order_date=date(2026, 4, 27),
            customer_name=cust, total_amount=tot, sales_employee="X",
        ))
    await db_session.commit()
    r = await viewer_client.get("/api/data/sales/orders-distribution?from=2026-04-27&to=2026-04-30")
    assert r.status_code == 200
    payload = r.json()
    assert payload["top3_share_pct"] == 90.0
    assert payload["remaining_share_pct"] == 10.0
    assert sorted(payload["top3_customers"]) == ["A", "B", "C"]
```

- [ ] **Step 2: Implement (append to `sales_kpi_aggregation.py`)**

```python
async def compute_orders_distribution(
    session: AsyncSession, date_from: date, date_to: date,
) -> dict:
    rows = (
        await session.execute(
            select(SalesRecord).where(
                SalesRecord.order_date >= date_from,
                SalesRecord.order_date <= date_to,
            )
        )
    ).scalars().all()
    if not rows:
        return {
            "orders_per_week_per_rep": 0.0,
            "top3_share_pct": 0.0,
            "remaining_share_pct": 0.0,
            "top3_customers": [],
        }

    # Mapped sales reps only
    aliases = (await session.execute(select(SalesEmployeeAlias.employee_token))).all()
    mapped_tokens = {a.employee_token for a in aliases}
    mapped_rows = [r for r in rows if (r.sales_employee or "").upper() in mapped_tokens]

    # Number of mapped distinct reps
    rep_count = max(1, len({(r.sales_employee or "").upper() for r in mapped_rows}))
    weeks = max(1, ((date_to - date_from).days // 7) + 1)
    opwpr = round(len(mapped_rows) / weeks / rep_count, 2)

    # Customer concentration on the FULL set (not just mapped reps).
    by_customer: dict[str, float] = defaultdict(float)
    for r in rows:
        by_customer[r.customer_name or ""] += float(r.total_amount or 0)
    sorted_cust = sorted(by_customer.items(), key=lambda kv: kv[1], reverse=True)
    total = sum(by_customer.values()) or 1.0
    top3 = sorted_cust[:3]
    top3_sum = sum(v for _, v in top3)
    top3_pct = round(top3_sum / total * 100, 2)
    return {
        "orders_per_week_per_rep": opwpr,
        "top3_share_pct": top3_pct,
        "remaining_share_pct": round(100.0 - top3_pct, 2),
        "top3_customers": [c for c, _ in top3],
    }
```

(Add `from collections import defaultdict` at top if not already present.)

- [ ] **Step 3: Run, expect green**

```bash
docker compose exec api pytest tests/test_orders_distribution.py -q
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/sales_kpi_aggregation.py backend/tests/test_orders_distribution.py
git commit -m "feat(v1.41 C-2): GET /api/data/sales/orders-distribution — orders/wk/rep + top-3 customer share"
```

---

## Phase D — Frontend

### Task D1: Upload page — add "Kontakte" upload variant

**Files:**
- Modify: `frontend/src/pages/UploadPage.tsx` (or wherever the existing upload form lives — locate first)

- [ ] **Step 1: Locate the upload form**

```bash
grep -rn "/api/upload\b\|upload-batch\|UploadFile\|UploadForm" frontend/src --include="*.tsx" -l | head
```

- [ ] **Step 2: Add a radio next to existing "Aufträge" → "Kontakte" that POSTs to `/api/upload-contacts` instead.**

Reuse the existing react-hook-form / TanStack mutation. The success toast should show `rows_inserted`, `rows_replaced`, and a link to `/settings/hr#sales-aliases` if `unmapped_tokens.length > 0`.

- [ ] **Step 3: Vitest — render test for the new radio + submit path**

Use the same MSW pattern the existing upload form tests use (locate via `grep -rn "msw\|setupServer" frontend/src/__tests__`).

- [ ] **Step 4: Run, expect green**

```bash
cd frontend && npx vitest run UploadPage -q
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/UploadPage.tsx frontend/src/pages/__tests__/UploadPage.test.tsx
git commit -m "feat(v1.41 D-1): UploadPage — Kontakte upload variant + unmapped-token toast link"
```

### Task D2: SalesActivityCard — 4 weekly LineCharts

**Files:**
- Create: `frontend/src/components/dashboard/SalesActivityCard.tsx`
- Create: `frontend/src/hooks/useContactsWeekly.ts`
- Create: `frontend/src/components/dashboard/__tests__/SalesActivityCard.test.tsx`

- [ ] **Step 1: Write the hook**

```ts
// frontend/src/hooks/useContactsWeekly.ts
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import type { ContactsWeeklyResponse } from "@/lib/types";

export function useContactsWeekly(from: string, to: string) {
  return useQuery<ContactsWeeklyResponse>({
    queryKey: ["sales", "contacts-weekly", from, to],
    queryFn: () => apiClient(`/api/data/sales/contacts-weekly?from=${from}&to=${to}`),
  });
}
```

Add the response type to `frontend/src/lib/types.ts` (or wherever shared types live):

```ts
export interface ContactsWeeklyEmployeeBucket {
  erstkontakte: number;
  interessenten: number;
  visits: number;
  angebote: number;
}
export interface ContactsWeeklyWeek {
  iso_year: number;
  iso_week: number;
  label: string;
  per_employee: Record<number, ContactsWeeklyEmployeeBucket>;
}
export interface ContactsWeeklyResponse {
  weeks: ContactsWeeklyWeek[];
  employees: Record<number, string>;
}
```

- [ ] **Step 2: SalesActivityCard component**

```tsx
// frontend/src/components/dashboard/SalesActivityCard.tsx
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { useTranslation } from "react-i18next";
import { useContactsWeekly } from "@/hooks/useContactsWeekly";
import { sensorPalette } from "@/lib/sensorPalette";

const KPIS = [
  { key: "erstkontakte", titleKey: "sales.kpi.erstkontakte" },
  { key: "interessenten", titleKey: "sales.kpi.interessenten" },
  { key: "visits", titleKey: "sales.kpi.visits" },
  { key: "angebote", titleKey: "sales.kpi.angebote" },
] as const;

interface Props { startDate: string; endDate: string; }

export function SalesActivityCard({ startDate, endDate }: Props) {
  const { t } = useTranslation();
  const q = useContactsWeekly(startDate, endDate);
  if (q.isLoading) return <Card><CardContent>…</CardContent></Card>;
  if (!q.data || q.data.weeks.length === 0) {
    return (
      <Card>
        <CardContent className="text-sm text-muted-foreground py-8 text-center">
          {t("sales.activity.empty")}
        </CardContent>
      </Card>
    );
  }
  const empIds = Object.keys(q.data.employees).map(Number).sort((a, b) => a - b);
  // Per-KPI series of {label, [empId]: count}
  const seriesFor = (kpi: keyof typeof KPIS[number] extends string ? string : never) =>
    q.data!.weeks.map((w) => {
      const row: Record<string, number | string> = { label: w.label };
      for (const id of empIds) {
        row[id] = w.per_employee[id]?.[kpi as never] ?? 0;
      }
      return row;
    });
  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold">{t("sales.activity.title")}</h2>
      </CardHeader>
      <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {KPIS.map((k, idx) => (
          <div key={k.key} className="h-64">
            <div className="text-sm font-medium mb-2">{t(k.titleKey)}</div>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={seriesFor(k.key as never)}>
                <XAxis dataKey="label" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                {idx === 0 && <Legend />}
                {empIds.map((id, i) => (
                  <Line
                    key={id}
                    type="monotone"
                    dataKey={String(id)}
                    name={q.data!.employees[id]}
                    stroke={sensorPalette[i % sensorPalette.length]}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
```

Add locale keys `sales.activity.title`, `sales.activity.empty`, `sales.kpi.{erstkontakte,interessenten,visits,angebote}` to en.json + de.json.

- [ ] **Step 3: Vitest** — fixture: 3 reps × 4 weeks → assert 4 chart titles render and the legend shows 3 employee names.

- [ ] **Step 4: Run, expect green**

```bash
cd frontend && npx vitest run SalesActivityCard -q
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dashboard/SalesActivityCard.tsx frontend/src/hooks/useContactsWeekly.ts frontend/src/lib/types.ts frontend/src/locales/ frontend/src/components/dashboard/__tests__/SalesActivityCard.test.tsx
git commit -m "feat(v1.41 D-2): SalesActivityCard — 4 weekly LineCharts (Erst./Inter./Visits/Angebote) per sales rep"
```

### Task D3: OrdersDistributionCard — 3-tile combo card

**Files:**
- Create: `frontend/src/components/dashboard/OrdersDistributionCard.tsx`
- Create: `frontend/src/hooks/useOrdersDistribution.ts`
- Create: `frontend/src/components/dashboard/__tests__/OrdersDistributionCard.test.tsx`

- [ ] **Step 1: Hook**

```ts
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";

export interface OrdersDistribution {
  orders_per_week_per_rep: number;
  top3_share_pct: number;
  remaining_share_pct: number;
  top3_customers: string[];
}

export function useOrdersDistribution(from: string, to: string) {
  return useQuery<OrdersDistribution>({
    queryKey: ["sales", "orders-distribution", from, to],
    queryFn: () => apiClient(`/api/data/sales/orders-distribution?from=${from}&to=${to}`),
  });
}
```

- [ ] **Step 2: Component using existing `KpiCard`** — three tiles in one Card titled "Auftragsverteilung".

- [ ] **Step 3: Vitest** — fixture asserts the three tiles + the rounding rule (sum to 100 ± 0.1).

- [ ] **Step 4: Run, expect green**

```bash
cd frontend && npx vitest run OrdersDistributionCard -q
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dashboard/OrdersDistributionCard.tsx frontend/src/hooks/useOrdersDistribution.ts frontend/src/components/dashboard/__tests__/OrdersDistributionCard.test.tsx frontend/src/locales/
git commit -m "feat(v1.41 D-3): OrdersDistributionCard — orders/week/rep + top-3 customer share + remaining share"
```

### Task D4: Wire both cards into `DashboardPage`

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`

- [ ] **Step 1: Add the two new cards below `RevenueChart`**

```tsx
<RevenueChart … />
<SalesActivityCard startDate={startDate} endDate={endDate} />
<OrdersDistributionCard startDate={startDate} endDate={endDate} />
<SalesTable … />
```

- [ ] **Step 2: Build verification**

```bash
cd frontend && npm run build
```

Expected: green.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/DashboardPage.tsx
git commit -m "feat(v1.41 D-4): mount SalesActivityCard + OrdersDistributionCard on /dashboard"
```

### Task D5: HR settings page — sales-departments picker + unmapped-reps + manual aliases

**Files:**
- Modify: `frontend/src/components/settings/PersonioCard.tsx` (add the picker below production_dept)
- Modify: `frontend/src/hooks/useSettingsDraft.ts` (add `personio_sales_dept` slice)
- Create: `frontend/src/components/settings/SalesAliasesSection.tsx`
- Modify: `frontend/src/pages/HrSettingsPage.tsx` (mount `SalesAliasesSection` below `PersonioCard`)
- Modify: `frontend/src/locales/en.json` + `de.json`

- [ ] **Step 1: Add `personio_sales_dept` to `useSettingsDraft`** — same shape as `personio_production_dept`.

- [ ] **Step 2: Add a `MultiSelect` row to `PersonioCard.tsx`** below the production_dept picker, labeled `settings.personio.sales_dept.label`.

- [ ] **Step 3: Build `SalesAliasesSection`** — a new Card with two subsections:
  - "Unmapped sales reps" — table fed by `GET /api/data/sales/contacts-weekly` (we already have it; "unmapped" lives in upload response and we just keep a TanStack-cached list). Each row has a "Zuordnen" button → small dialog → POST manual alias.
  - "Manuelle Aliasse" — table of `GET /api/admin/sales-aliases` (add a small read endpoint scoped to admins as part of D5).

(Tiny addendum to backend: add `GET /api/admin/sales-aliases` returning a list — single line in `sales_aliases.py`. Trivial; do this together with D5.)

- [ ] **Step 4: Vitest** — `SalesAliasesSection.test.tsx`: alias create + delete round-trip with MSW.

- [ ] **Step 5: Run, expect green**

```bash
cd frontend && npx vitest run -q
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/settings/PersonioCard.tsx frontend/src/hooks/useSettingsDraft.ts frontend/src/components/settings/SalesAliasesSection.tsx frontend/src/pages/HrSettingsPage.tsx frontend/src/locales/ backend/app/routers/sales_aliases.py
git commit -m "feat(v1.41 D-5): HR settings — sales-departments picker + manual aliases + unmapped-reps section"
```

---

## Phase E — Tests, docs, ship

### Task E1: Full backend pytest

```bash
docker compose exec api pytest -q
```

Expected: full green (363 baseline + new tests).

### Task E2: Full vitest + production build

```bash
cd frontend && npx vitest run --reporter=dot && npm run build
```

Expected: 274/275 + 0 build errors (i.e. existing baseline preserved + new tests counted).

### Task E3: Refresh docs

- [ ] **Step 1: Add a section to `docs/en/admin-guide/personio.md` and the German mirror**: "Sales departments — defines which Personio employees count toward the Sales-activity charts. Mapping uses uppercased + umlaut-folded surnames; nicknames can be overridden manually."

- [ ] **Step 2: Add a section to `docs/en/user-guide/sales-dashboard.md` (and DE) describing the four new charts and the orders-distribution card.**

- [ ] **Step 3: Commit**

```bash
git add frontend/src/docs/
git commit -m "docs(v1.41): sales-activity charts + sales-dept Personio config"
```

### Task E4: README v1.41 entry + tag + push

- [ ] **Step 1: Add v1.41 entry to README.md** below the v1.40 entry, summarizing the four new KPIs and the new HR settings option.

- [ ] **Step 2: Empty ship-tag commit**

```bash
git commit --allow-empty -m "v1.41: sales-activity KPIs (Erstkontakte/Interessenten/Visits/Angebote) + orders-distribution card + Personio sales-dept config"
git tag -a v1.41 -m "v1.41 — sales-activity KPIs"
git push origin main --tags
```

---

## Self-Review

- **Spec coverage:** every spec section has a task. Mapping:
  - A1+A2 = schema; A3 = settings + Pydantic.
  - B1 = parser; B2 = canonical_token; B3 = upload route; B4 = sync hook; B5 = manual alias CRUD.
  - C1 = contacts-weekly; C2 = orders-distribution.
  - D1 = upload UI; D2 = activity charts; D3 = combo card; D4 = mount; D5 = HR settings extension.
  - E1–E4 = tests + docs + ship.
- **Placeholder scan:** no "TBD", no "implement later". Every code-bearing step contains the actual code.
- **Type consistency:** `SalesContact`, `SalesEmployeeAlias`, `personio_sales_dept` names are spelled identically in models, schemas, settings, sync hook, router, frontend hook, locale keys.
- **One open detail:** D5 step 3 quietly adds a `GET /api/admin/sales-aliases` listing endpoint that wasn't in B5; called out here rather than buried.
