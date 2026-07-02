# ATR module — Phase A: reference data foundation

**Date:** 2026-06-25
**Status:** approved (brainstorm)
**Driver:** ACM Quality must produce two documents from each Diehl delivery note (Lieferschein): an **ATR/CoC** (Acceptance Test Report with Weight Report + Certificate of Conformity) and a **Containerbeschriftung** (Word container label). Most of the ATR content (part names, drawing numbers/issues, reference weights, header constants) is not in the Lieferschein — it lives in a set of pre-built Excel "ATR" templates maintained by QA on the fileserver. This phase imports the parts out of those workbooks into LumeApps as **one editable global parts catalog**, plus a **single structural template**, the reference foundation every later phase reads from.

This is **Phase A of three** (see `## Roadmap context`). It delivers no document generation and no fileserver/scheduler integration — only the reference master and its editing UI.

## Goal

A new `atr` module in LumeApps with:

1. **One global parts catalog** (`atr_part`) — the full, deduplicated list of every part found across the reference workbooks, each row recording the **source file** it came from, fully editable.
2. **One structural template** (`atr_template`, singleton) — the ATR layout/structure plus the constant header-block defaults, editable.

An Excel importer reads each reference workbook, upserts its parts into the catalog (by part number), and seeds/updates the template defaults. An admin UI lets the operator search/edit the catalog and edit the template defaults. Import is by uploading `.xlsx` files (the fileserver mount comes in Phase C).

## Value sourcing (the model in one line)

> The **template** supplies *structure and static labels only*. Every **value** in a generated ATR comes from **the DB** (parts catalog + header defaults) **or the Lieferschein** (PO, MSN, BA, set title, selected parts, quantities, dates, container/ATR numbers). No part data lives in the template.

## Non-goals (deferred to later phases)

- **Phase B:** Lieferschein PDF parsing, matching positions → catalog parts, the review/approve screen, ATR `.xlsx`+PDF generation (filling the structural template), Containerbeschriftung `.docx` generation, LibreOffice in the backend image.
- **Phase C:** SMB/AD mount of `Z:\…\Input` / `Output`, the settings page (paths, poll interval, auto/review mode), the scheduler scan job, archiving processed files.
- Keeping a separate parts list per workbook/scenario. There is **one** catalog; re-importing another workbook merges into it.
- Editing hidden sheets. Only the single **visible** sheet of each workbook is read.

## Roadmap context

```
Phase A (this spec)  Reference foundation: import 12 xlsx → one global parts catalog + one structural template
Phase B              Generate from a Lieferschein (manual trigger): parse → match catalog → review → fill template → ATR(.xlsx+PDF) + label(.docx)
Phase C              Fileserver + automation: SMB/AD mount, settings page, scheduler scan, write-to-Output, archive
```

Each phase gets its own spec → plan → implementation cycle.

## Source-file analysis (what the importer must handle)

Verified across all 12 reference workbooks in
`Z:\1300 - Qualität\…\DIEHL\A350\ATR_Acceptance Test Report\`. The structure is **identical across all 12** — only the header *values* and the part *list* differ, which is exactly why one structural template + one merged catalog is the right model.

- **3 sheets per workbook**, exactly **one visible**; the other two hidden. Read the visible sheet only. The visible sheet's *name* is unreliable (often `CCRC 6 BED` even for 8-Bett/FCRC content) — **cell `A11` (set title) is the authoritative config label.**
- **Header block — fixed cell map** (col A = label, col D/G = value):
  | Cell | Meaning | Example |
  |------|---------|---------|
  | `D1` | Customer | `Diehl Aviation Laupheim GmbH` |
  | `F1`/`G1`/`I1`/`J1`/`K1` | Purchase Order No. (split across cells; templated `4500…`) | `4500… 79 - 0830 - 94` |
  | `D2` | AC Programme | `A350 XWB` |
  | `G2` | MSN (templated `…`) | `830` |
  | `G3` | ATA Chapter | `25` |
  | `D3` | Work Package / reference text | `Soft Furnishing for Flight and Cabin Crew Rest Compartments` |
  | `D4` | Purchaser Spec | `PTS 2552 0015 01, Issue 02` |
  | `G4` | NSCM-Code | `C9312` |
  | `D5` | ATP | `ACM-A350CRC-ATP-002 Issue 02` |
  | `D6` | Supplier Spec | `ACM-A350CRC-SES-003 Issue 03` |
  | `D7` | Reference No. | `PA-CO-BTS-2010-042-01-CRC_Soft Furnishing` |
  | `D8` | Supplier | `ACM GmbH - Woringer Straße 11 - 87700 Memmingen` |
  | `G8` | Customer Spec | `N/A` |
  | `D9` | Manufacturing Process Ref. / WO No. (templated `1021…`) | `1024738` |
  | `A11` | Set title (per-delivery, NOT a default) | `SET 6 BED CCRC` |
  | `F12` | Weighing Equipment | `Plattenwaage PW015` |
  | totals block | Max. Guaranteed weight | `211` |

  Header fields `D1`–`G8` + `F12` are **constant** across the files (Customer, Work Package, specs, ATA, NSCM, Supplier, equipment) → they seed the **template defaults**. Fields that vary per delivery (`A11` set title, PO, MSN, WO No, Max-guaranteed weight which depends on 6/8-bed) are **not** stored as defaults — Phase B fills them from the Lieferschein/input.

- **Table header always at row 13:** `A`=PO Pos, `B`=Supplier Article Code, `C`=Part Number / Index, `D`=Part Name, `E`=Serial Number, `F`=Drawing Number / Issue, `G`=Qty, `H`=Weight [kg], `I`–`N`=inspection columns.
- **Parts start at row 15.** A row is a **part** when col `C` starts with `VR`. A row is a **section header** (`SEC. LINING`, `CURTAIN`, `HEAD`, `CARPET`, `MATTRESS`) when col `A` holds text and `C` is empty — it sets the `category` for parts beneath it.
- **Quirks to absorb:**
  - Part-number spacing/zero-padding is inconsistent (`VR11S 1010 048 000`, drawing `VR11S1010-021/A` vs `VR11S 1010-21/A`). Store the raw string **and** a normalized digits-only key (`part_number_norm`) — the catalog's unique key and the Phase-B match key.
  - Trailing spaces in many cells (`'N/A '`, `'SEC LINING BED 03'`). Trim on import.
  - Part counts vary 3 → 101 per file; the merged catalog is the union (≈120–150 distinct parts expected).
  - The same part number appears in several files, sometimes with a different weight or drawing issue (revisions). On merge this is an **upsert** keyed by `part_number_norm` — last import wins, and `source_filename` + `imported_at` record which file/when the current values came from (provenance). Differences are surfaced in the import preview so the operator decides before committing.
  - Encoding: read with openpyxl (UTF-8 safe).

## Data model

New module `backend/app/models/atr.py`, tables created by one Alembic migration `v1_63_atr_reference` with `down_revision = "v1_62_tippspiel"` (current head as of this spec — re-verify head at implementation time).

### `atr_part` — global parts catalog

One row per distinct part (by `part_number_norm`). The full list, editable.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `Integer` PK | |
| `part_number` | `String(60)` NOT NULL | col C, raw (display form) |
| `part_number_norm` | `String(40)` NOT NULL **UNIQUE** | digits-only; catalog key + Phase-B match key |
| `supplier_article_code` | `String(40)` | col B |
| `part_name` | `String(200)` | col D, trimmed |
| `drawing_number_issue` | `String(60)` | col F |
| `default_weight_kg` | `Numeric(8,3)` NULL | col H — nominal/reference weight; Phase B may override per delivery |
| `qty` | `Integer` NOT NULL DEFAULT 1 | col G |
| `category` | `String(40)` NULL | nearest section header above the row |
| `po_pos` | `String(20)` NULL | **editable**; empty on import (not in source — see open item) |
| `source_filename` | `String(255)` NOT NULL | **provenance** — file the current values last came from |
| `imported_at` | `DateTime(tz)` NOT NULL | when those values were imported |
| `updated_at` | `DateTime(tz)` NOT NULL | last manual edit |

Index `ix_atr_part_norm` is the UNIQUE constraint on `part_number_norm`. (A `UNIQUE` means re-import upserts rather than duplicates — the merge mechanism.)

### `atr_template` — single structural template (singleton, `id = 1`)

Editable header-block defaults + the stored structural workbook used (in Phase B) to render. `CHECK (id = 1)` singleton, matching the repo's `app_settings` / `personio_sync_meta` pattern.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `Integer` PK `CHECK (id = 1)` | |
| `customer` | `String(200)` | `D1` |
| `ac_programme` | `String(100)` | `D2` |
| `work_package` | `Text` | `D3` |
| `purchaser_spec` | `String(200)` | `D4` |
| `atp` | `String(200)` | `D5` |
| `supplier_spec` | `String(200)` | `D6` |
| `reference_no` | `String(200)` | `D7` |
| `supplier` | `String(200)` | `D8` |
| `customer_spec` | `String(100)` | `G8` |
| `nscm_code` | `String(40)` | `G4` |
| `ata_chapter` | `String(20)` | `G3` |
| `weighing_equipment` | `String(100)` | `F12` |
| `qa_signer_default` | `String(100)` NULL | e.g. `Cordula Kesseler i.A.` (from the example output; editable) |
| `structure_filename` | `String(255)` NULL | original name of the workbook designated as the structural template |
| `structure_xlsx` | `BYTEA` NULL | the designated workbook's bytes, stored for Phase B to fill (kept verbatim to preserve formatting) |
| `updated_at` | `DateTime(tz)` NOT NULL | |

Seeded with a single `id = 1` row by the migration (all-null defaults). The first import (or an explicit "use as structural template" action) populates it. **Phase A stores the structural workbook bytes but does not fill/render it** — that is Phase B.

## Backend

### `services/atr_reference_import.py`

Pure parsing, no DB. `parse_workbook(file_bytes, source_filename) -> ParsedWorkbook` carrying: the header-default fields, an ordered list of parsed parts, and a list of **warnings** (e.g. "row 47: col C empty, skipped"; "no totals block found"). Rules per `## Source-file analysis`. Uses `openpyxl` (already a stack dependency via pandas/openpyxl). Reads the **visible** sheet; errors clearly if zero or multiple visible sheets, or if row-13 headers don't match the expected layout.

Helpers: `norm_partno(s)` = digits only; trim all strings; weights via `Decimal`.

### `routers/atr.py`

Router-level admin gate (repo convention in `CLAUDE.md` → "Auth gate placement"; mirror `routers/sensors.py`):

```python
router = APIRouter(prefix="/api/atr", tags=["atr"],
    dependencies=[Depends(get_current_user), Depends(require_admin)])
```

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/atr/import/preview` | multipart `.xlsx` (one or many) → parse → **preview**, no commit: for each file, the parsed header defaults + parts split into **new** vs **updated** (value diffs vs current catalog) + warnings |
| `POST` | `/api/atr/import/commit` | apply a previewed import: upsert parts by `part_number_norm` (set `source_filename`/`imported_at`); optionally update template defaults; optionally set the structural workbook |
| `GET` | `/api/atr/parts` | list/search the full catalog (query by part number, name, category; paginated) |
| `GET` | `/api/atr/parts/{id}` | one part |
| `POST` | `/api/atr/parts` | add a part manually |
| `PATCH` | `/api/atr/parts/{id}` | edit a part (po_pos, weight, drawing, name, category, …) |
| `DELETE` | `/api/atr/parts/{id}` | delete a part |
| `GET` | `/api/atr/template` | the singleton template defaults (+ whether a structural workbook is set; bytes not returned) |
| `PATCH` | `/api/atr/template` | edit header defaults / qa_signer_default |
| `POST` | `/api/atr/template/structure` | upload/designate the structural workbook (stored as `structure_xlsx`) |

Import is **preview→commit** so the operator sees new-vs-updated parts and warnings before anything is written. Schemas in `backend/app/schemas/atr.py` (Pydantic v2): `AtrPartRead`, `AtrPartCreate`, `AtrPartUpdate`, `AtrTemplateRead`, `AtrTemplateUpdate`, `AtrImportPreview` (per-file: header, new[], updated[], warnings[]), `AtrImportCommit`.

Register the router in `main.py` alongside the others. No scheduler changes in Phase A.

## Frontend

New page under the existing app shell (mirror Sensors/HR page structure). Routes:

```
/atr                → parts catalog: searchable/filterable table (part no, name, category, drawing, weight, po_pos, source file), inline edit, add/delete
/atr/import         → upload one or many .xlsx → preview (per file: new vs updated parts, value diffs, warnings) → commit
/atr/template       → edit template header defaults + qa_signer; show/replace the designated structural workbook
```

- Reuse existing primitives: shadcn Card/Table/Button/Select/Input, the ActionBar + unsaved-changes guard (`useUnsavedGuard`) used by settings pages, TanStack Query, the `queryKeys`/`api.ts` conventions.
- The catalog table shows **`source_filename`** per row so provenance is visible at a glance.
- Launcher entry "ATR" (admin-only visibility), consistent with other modules in `LauncherPage`.
- i18n: add `atr.*` keys to `en.json` + `de.json`. Primary users are German-speaking QA.

## Error handling

- Importer never throws on a single bad row — it collects warnings and skips, surfacing them in the preview so the operator decides whether to commit.
- Hard errors (not a `.xlsx`, no/multiple visible sheets, row-13 header missing / unrecognized layout) → `400` with a clear message; nothing written.
- All writes transactional; `DELETE` on a part is a single-row delete (no cascade — catalog rows are independent).
- Editing the singleton `atr_template` never inserts a second row (guarded by `CHECK (id = 1)` + upsert-on-id-1).

## Testing

Backend (pytest, mirroring existing module test style):

- `test_atr_reference_import.py` — parse a **fixture workbook** (trimmed copies committed under `backend/tests/fixtures/atr/`, NOT the live Z: files): header-default extraction, part count, category assignment, `part_number_norm`, trimming, weight Decimal parsing, warning collection on a malformed row.
- `test_atr_merge.py` — importing two fixtures where a shared part number has a different weight asserts upsert (one catalog row, newest `source_filename`, value updated) and that the preview classifies it as **updated** not **new**.
- `test_atr_router.py` — preview→commit, catalog list/search, part add/edit/delete, template GET/PATCH, structural-workbook upload, 400 on bad file, singleton invariant.
- `test_atr_admin_gate.py` — every `/api/atr/*` route rejects non-admin (mirror `test_sensors_admin_gate.py`; satisfies the CI dep-audit guard in `test_admin_gate_audit.py`).

Frontend: focused tests for the import preview (new vs updated rendering) and the catalog inline-edit (mirror `HrSettingsPage.test.tsx`). Commit ≥1 fixture workbook so tests run without the fileserver.

**Acceptance check (one-off, not a unit test):** import all 12 live workbooks via the UI → confirm one merged catalog of ≈120–150 distinct parts, then confirm the 8 carpet parts from the example Lieferschein (`LIEFERSCHEIN_10005_20189798.pdf`) resolve by `part_number_norm` to the expected drawing numbers (`VR11S 1010-27/A`, `-28/A`, `-10/D`, …) — proving the Phase-B match key ahead of Phase B.

## Open items (carried, not blocking Phase A)

1. **PO-Pos source** (`050, 300, 340…`): not in the Lieferschein or the templates. Phase A stores `po_pos` as an editable per-part catalog field (blank on import); the operator maintains it. Revisit in Phase B whether it can be derived from the Diehl PO.
2. **ATR number** (`ATR-4545-01`), **container number** (`AK111XXX`), **set title** (`SET 6 BED CCRC`), **PO/MSN/WO** and **dates**: per-delivery values — belong to Phase B's delivery record / Lieferschein input, not the catalog or template defaults. Noted here so they are not modeled in Phase A.

## Throwaway scripts

The exploration scripts under `scripts/atr_*.py` (`atr_dump_xlsx`, `atr_scan_parts`, `atr_probe_structure`) were analysis aids. Delete them or relocate under `scripts/atr/` before Phase A merges — not part of the module.
