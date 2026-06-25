# ATR module — Phase A: reference data foundation

**Date:** 2026-06-25
**Status:** approved (brainstorm)
**Driver:** ACM Quality must produce two documents from each Diehl delivery note (Lieferschein): an **ATR/CoC** (Acceptance Test Report with Weight Report + Certificate of Conformity) and a **Containerbeschriftung** (Word container label). Most of the ATR content (part names, drawing numbers/issues, reference weights, header constants) is not in the Lieferschein — it lives in a set of pre-built Excel "ATR" templates maintained by QA on the fileserver. This phase imports those templates into LumeApps as **editable reference data**, the foundation every later phase reads from.

This is **Phase A of three** (see `## Roadmap context`). It delivers no document generation and no fileserver/scheduler integration — only the reference master and its editing UI.

## Goal

A new `atr` module in LumeApps with two tables (`atr_template`, `atr_template_part`), an Excel importer that turns each reference workbook into one editable template + its parts, and an admin UI to view and edit templates, header fields, and parts. Import is by uploading `.xlsx` files (the fileserver mount comes in Phase C).

## Non-goals (deferred to later phases)

- **Phase B:** Lieferschein PDF parsing, matching positions → parts, the review/approve screen, ATR `.xlsx`+PDF generation, Containerbeschriftung `.docx` generation, LibreOffice in the backend image.
- **Phase C:** SMB/AD mount of `Z:\…\Input` / `Output`, the settings page (paths, poll interval, auto/review mode), the scheduler scan job, archiving processed files.
- Merging parts across templates into a single global parts master. Each workbook stays its own template (faithful to the source artifacts; same part legitimately differs in weight/drawing-issue between scenarios).
- Editing hidden sheets. Only the single **visible** sheet of each workbook is imported.

## Roadmap context

```
Phase A (this spec)  Reference foundation: import 12 xlsx → editable template + parts master
Phase B              Generate from a Lieferschein (manual trigger): parse → match → review → ATR(.xlsx+PDF) + label(.docx)
Phase C              Fileserver + automation: SMB/AD mount, settings page, scheduler scan, write-to-Output, archive
```

Each phase gets its own spec → plan → implementation cycle.

## Source-file analysis (what the importer must handle)

Verified across all 12 reference workbooks in
`Z:\1300 - Qualität\…\DIEHL\A350\ATR_Acceptance Test Report\`:

- **3 sheets per workbook**, exactly **one visible**; the other two hidden. Import the visible sheet only. The visible sheet's *name* is unreliable (often `CCRC 6 BED` even for 8-Bett/FCRC content) — **cell `A11` (set title) is the authoritative config label.**
- **Header block — fixed cell map** (col A = label, col D/G = value):
  | Cell | Meaning | Example |
  |------|---------|---------|
  | `D1` | Customer | `Diehl Aviation Laupheim GmbH` |
  | `F1`/`G1`/`I1`/`J1`/`K1` | Purchase Order No. (split across cells; templated as `4500…`) | `4500… 79 - 0830 - 94` |
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
  | `A11` | **Set title (config label)** | `SET 6 BED CCRC` |
  | `F12` | Weighing Equipment | `Plattenwaage PW015` |
  | `H81`* | Max. Guaranteed weight | `211` |

  *The totals block (`Total weight`, `Max. Guaranteed weight`, `Test Results`) sits a few rows below the last part; located by scanning col F/A for the labels rather than a fixed row, because the row shifts with part count.

- **Table header always at row 13:** `A`=PO Pos, `B`=Supplier Article Code, `C`=Part Number / Index, `D`=Part Name, `E`=Serial Number, `F`=Drawing Number / Issue, `G`=Qty, `H`=Weight [kg], `I`–`N`=inspection columns (Dimension, Visual, Material, Documents, Identification, Inspected).
- **Parts start at row 15.** A row is a **part** when col `C` (part number) starts with `VR`. A row is a **section header** (e.g. `SEC. LINING`, `CURTAIN`, `HEAD`, `CARPET`, `MATTRESS`) when col `A` holds text and `C` is empty — it sets the `category` for the parts beneath it.
- **Quirks to absorb:**
  - Part-number spacing/zero-padding is inconsistent (`VR11S 1010 048 000`, drawing `VR11S1010-021/A` vs `VR11S 1010-21/A`). Store the raw string **and** a normalized digits-only key (`part_number_norm`) for Phase-B matching.
  - Trailing spaces in many cells (`'N/A '`, `'SEC LINING BED 03'`). Trim on import.
  - Part counts vary 3 → 101. Same part appears in many files with slightly different weight / drawing issue — expected; do not dedupe.
  - Encoding: file paths and German text contain umlauts; read with openpyxl (UTF-8 safe), not pdftotext.

## Data model

New module `backend/app/models/atr.py`, tables created by one Alembic migration `v1_63_atr_reference` with `down_revision = "v1_62_tippspiel"` (current head as of this spec — re-verify head at implementation time).

### `atr_template`

One row per imported workbook (its visible sheet).

| Column | Type | Notes |
|--------|------|-------|
| `id` | `Integer` PK | |
| `name` | `String(200)` NOT NULL UNIQUE | Operator-facing label; defaults to `A11` title, editable |
| `compartment` | `String(8)` NOT NULL | `CCRC` or `FCRC`; operator-confirmed on import |
| `bed_config` | `String(8)` NULL | `6`, `8`, or NULL (e.g. Urgent Parts) |
| `variant` | `String(40)` NOT NULL | `standard` / `inkl_neuteile` / `mit_verstaerkung` / `urgent` / `neue_teile` — operator-set, free-ish |
| `set_title` | `String(200)` | raw `A11` |
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
| `max_guaranteed_weight_kg` | `Numeric(8,3)` NULL | totals block |
| `source_filename` | `String(255)` NOT NULL | original upload name |
| `imported_at` | `DateTime(tz)` NOT NULL | |
| `updated_at` | `DateTime(tz)` NOT NULL | |

Every header field above is **editable** via the UI (the values are templated placeholders in the source — e.g. PO `4500…`, MSN `…` — so Phase B overrides per delivery anyway; these are defaults).

### `atr_template_part`

| Column | Type | Notes |
|--------|------|-------|
| `id` | `Integer` PK | |
| `template_id` | `Integer` FK → `atr_template.id` `ON DELETE CASCADE` NOT NULL | |
| `row_order` | `Integer` NOT NULL | preserves source ordering for display + generation |
| `category` | `String(40)` NULL | nearest section header above the row |
| `po_pos` | `String(20)` NULL | **editable**; empty on import (not in source — see open item) |
| `supplier_article_code` | `String(40)` | col B |
| `part_number` | `String(60)` NOT NULL | col C, raw |
| `part_number_norm` | `String(40)` NOT NULL | digits-only of `part_number`; **Phase-B match key** |
| `part_name` | `String(200)` | col D, trimmed |
| `serial_number` | `String(40)` | col E (usually `N/A`) |
| `drawing_number_issue` | `String(60)` | col F |
| `qty` | `Integer` NOT NULL DEFAULT 1 | col G |
| `default_weight_kg` | `Numeric(8,3)` NULL | col H |

Indexes: `ix_atr_template_part_template` on `template_id`; `ix_atr_template_part_norm` on `part_number_norm` (Phase-B lookups). No unique constraint on `part_number_norm` — duplicates across templates are valid, and a single template can legitimately list the same part twice (different beds).

## Backend

### `services/atr_reference_import.py`

Pure parsing, no DB. `parse_workbook(file_bytes, source_filename) -> ParsedTemplate` where `ParsedTemplate` carries the header fields + an ordered list of parsed parts + a list of **warnings** (e.g. "row 47: col C empty, skipped", "no totals block found"). Rules per `## Source-file analysis`. Uses `openpyxl` (already a stack dependency via pandas/openpyxl). Reads the **visible** sheet (`ws.sheet_state == "visible"`); errors clearly if zero or multiple visible sheets.

Normalization helpers: `norm_partno(s)` = digits only; trim all strings; parse German/Excel numerics for weights via `Decimal`.

### `routers/atr.py`

Router-level admin gate (matches the repo convention in `CLAUDE.md` → "Auth gate placement"; mirror `routers/sensors.py`):

```python
router = APIRouter(prefix="/api/atr", tags=["atr"],
    dependencies=[Depends(get_current_user), Depends(require_admin)])
```

Endpoints (all admin-only):

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/atr/templates/import` | multipart `.xlsx` upload → parse → **preview** (no commit): returns parsed header, parts, warnings, plus a guessed `compartment`/`bed_config`/`variant` from filename + `A11` |
| `POST` | `/api/atr/templates` | commit a previewed import (body = confirmed header + parts + labels) → insert template + parts |
| `GET` | `/api/atr/templates` | list templates (id, name, compartment, bed_config, variant, part count, imported_at) |
| `GET` | `/api/atr/templates/{id}` | one template + its parts |
| `PATCH` | `/api/atr/templates/{id}` | edit header fields |
| `DELETE` | `/api/atr/templates/{id}` | delete template (cascades parts) |
| `PATCH` | `/api/atr/templates/{id}/parts/{part_id}` | edit one part (po_pos, weight, drawing, name, …) |
| `POST` | `/api/atr/templates/{id}/parts` | add a part row |
| `DELETE` | `/api/atr/templates/{id}/parts/{part_id}` | delete a part row |

Import is a **two-step preview→commit** so the operator confirms the auto-detected compartment/bed/variant and reviews warnings before anything is written. Re-importing the same `source_filename` is offered as "replace existing template" (delete + recreate) vs "create new".

Schemas in `backend/app/schemas/atr.py` (Pydantic v2): `AtrTemplateRead`, `AtrTemplatePartRead`, `AtrTemplateImportPreview`, `AtrTemplateCreate`, `AtrTemplateUpdate`, `AtrTemplatePartUpdate`, `AtrTemplatePartCreate`.

Register the router in `main.py` alongside the others. No scheduler changes in Phase A.

## Frontend

New page under the existing app shell (mirror how Sensors/HR pages are structured). Routes:

```
/atr                      → templates list (table: name, compartment, bed, variant, #parts, imported)
/atr/import               → upload .xlsx → preview (detected header + parts + warnings) → confirm labels → commit
/atr/templates/:id        → template detail: editable header card + editable parts table (inline edit, add/delete row)
```

- Reuse existing primitives: shadcn Card/Table/Button/Select, the ActionBar + unsaved-changes guard pattern (`useUnsavedGuard`) already used by settings pages, TanStack Query for data, the `queryKeys`/`api.ts` conventions.
- Launcher entry for "ATR" (admin-only visibility), consistent with other modules in `LauncherPage`.
- i18n: add `atr.*` keys to `en.json` + `de.json`. Primary users are German-speaking QA — German labels matter.

## Error handling

- Importer never throws on a single bad row — it collects warnings and skips, surfacing them in the preview so the operator decides whether to commit.
- Hard errors (not a `.xlsx`, no visible sheet, row-13 header missing / unrecognized layout) → `400` with a clear message; nothing written.
- All writes are transactional (template + its parts in one commit); `DELETE` cascades via FK.
- Unique `name` conflict → `409` with a clear message.

## Testing

Backend (pytest, mirroring existing module test style):

- `test_atr_reference_import.py` — parse a **fixture workbook** (a trimmed copy committed under `backend/tests/fixtures/atr/`, NOT the live Z: files): asserts header field extraction, part count, category assignment, `part_number_norm`, trimming, weight Decimal parsing, and warning collection on a deliberately malformed row.
- `test_atr_router.py` — preview→commit flow, list/get, header PATCH, part add/edit/delete, cascade on template delete, 400 on bad file, 409 on duplicate name.
- `test_atr_admin_gate.py` — every `/api/atr/*` route rejects non-admin (mirror `test_sensors_admin_gate.py`; satisfies the CI dep-audit guard in `test_admin_gate_audit.py`).

Frontend: a focused test for the import preview→confirm render and the parts inline-edit (mirror `HrSettingsPage.test.tsx`). Provide ≥1 committed fixture workbook so tests run without the fileserver.

**Verification of the real data:** as a one-off acceptance check (not a unit test), import all 12 live workbooks via the UI and confirm the 8 carpet parts from the example Lieferschein (`LIEFERSCHEIN_10005_20189798.pdf`) resolve by `part_number_norm` to the expected drawing numbers (`VR11S 1010-27/A`, `-28/A`, `-10/D`, …) — the Phase-B match key proven ahead of Phase B.

## Open items (carried, not blocking Phase A)

1. **PO-Pos source** (`050, 300, 340…`): not in the Lieferschein or the templates. Phase A stores `po_pos` as an editable per-part field (blank on import); the operator maintains it. Revisit in Phase B whether it can be derived from the Diehl PO instead.
2. **ATR number** (`ATR-4545-01`) and **container number** (`AK111XXX`): per-delivery values — belong to Phase B's delivery record, not the template. Noted here only so they are not modeled in Phase A.

## Throwaway scripts

The exploration scripts under `scripts/atr_*.py` (`atr_dump_xlsx`, `atr_scan_parts`, `atr_probe_structure`) were analysis aids. Either delete them or relocate under `scripts/atr/` before Phase A merges — they are not part of the module.
