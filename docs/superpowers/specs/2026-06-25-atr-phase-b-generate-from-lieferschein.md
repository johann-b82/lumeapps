# ATR module — Phase B: generate documents from a Lieferschein

**Date:** 2026-06-25
**Status:** approved (brainstorm)
**Driver:** With the Phase A reference foundation in place (one global parts catalog + one structural ATR template), Phase B delivers the core value: read a Diehl delivery note (Lieferschein), enrich its positions from the catalog, let an operator review, and **generate the two output documents** — the ATR/CoC (Excel filled from the template + a PDF) and the Containerbeschriftung (Word label). Trigger is manual in Phase B (upload a PDF, or pick one from a configured input directory); the automatic scheduler scan + SMB/AD fileserver mount + write-to-Output remain **Phase C**.

Builds on Phase A (`feat/atr-module`): `atr_part` (catalog, unique `part_number_norm`), `atr_template` (singleton: header defaults + `structure_xlsx` bytes), the parser/`norm_partno`, and the admin-gated `/api/atr` module.

## Goal

A manual end-to-end pipeline: **Lieferschein → parse → match catalog → persist a draft delivery → review/edit → generate ATR (.xlsx + .pdf) + Containerbeschriftung (.docx) → download.** Two new tables persist each delivery and its line items. Unmatched positions never block generation — they are emitted with a **red fill + warning** in the ATR so the operator fixes them in Excel.

## Non-goals (Phase C and beyond)

- The scheduler scan job and automatic processing of new files.
- SMB/AD mount of the real `Z:\…\Input` / `Output` shares (Phase B reads a plain filesystem path; Phase C swaps in the AD-authenticated mount).
- Writing generated documents to an `Output` directory (Phase B downloads them; Phase C auto-writes + archives the input).
- A Settings page for paths/interval/mode (Phase C). Phase B uses an `ATR_INPUT_DIR` env var for the input-directory mode.
- Editing the catalog/template (that is Phase A's UI).

## Decisions (locked in brainstorm)

1. **ATR generation = template-as-frame.** Use the stored `structure_xlsx` for the header block, table header, totals, and certification formatting; **write the delivery's matched parts into the table region** (copying a template part-row's cell style), grouped by category. Robust to any matched part regardless of which template variant it originated from.
2. **Two input modes, both manual:** (a) upload the Lieferschein PDF; (b) list + pick a PDF from a configured input directory (`ATR_INPUT_DIR`).
3. **Unmatched positions do not block.** Generate anyway; mark those rows with a red fill + a warning string so the operator corrects them in the produced Excel.
4. **ATR document number is editable, prefilled, manual** (no auto-increment).

## Infrastructure (small — most already present)

The backend image already has LibreOffice (core/impress/draw) + poppler-utils + Carlito/Caladea fonts (for the signage PPTX feature). Phase B adds:

- **`libreoffice-calc`** to `backend/Dockerfile` — verified necessary: the current packages cannot load `.xlsx` (`soffice --convert-to pdf` of an xlsx fails "source file could not be loaded"; Calc filter is missing). One apt line alongside the existing `libreoffice-impress`.
- **`python-docx`** to `backend/requirements.txt` (for the Word label).
- **Lieferschein PDF parsing reuses poppler `pdftotext`** (already installed) — no new Python PDF dependency.
- An `ATR_INPUT_DIR` env var (optional) in `docker-compose.yml` for the input-directory mode; unset disables that mode.

xlsx→PDF conversion mirrors the **existing signage LibreOffice conversion** invocation (`soffice --headless --convert-to pdf`); reuse that pattern/concurrency guard rather than inventing a new one.

## Source-document analysis (parser contract)

### Lieferschein (input) — verified against `LIEFERSCHEIN_10005_20189798.pdf`

Text-based PDF; `pdftotext -layout` extracts it cleanly. Structure:

- **Header:** `LIEFERSCHEIN`, `Nr.  20189798`, `Datum  08.06.2026`, `Kunden Nr.  10005`, `Bearbeiter  Ralf Zettler`; recipient `Diehl Aviation Laupheim GmbH`.
- **Per position** (repeating block):
  - A line `^\s*(\d+)\s+(\d+)\s+(\d+)\s+(STK|\w+)\b` → **Pos**, **Artikel** (supplier article code), **Menge** (qty), **ME** (unit).
  - **Bezeichnung** — the part name line(s) following (e.g. `CARPET EMERG. EXIT HATCH`), sometimes a German translation line after it (`TEPPICH ...`); take the first as the name.
  - `Bauteil-Index:` *or* `Bauteilindex:` → **index** (e.g. `D`, `A`).
  - `Ihre Nr.\s*(\S+)` → Diehl **part number** (e.g. `VR11S1010016000`). Its digits-only form (`norm_partno`) is the catalog match key.
  - `Auftrag Nr.\s*(\d+)\s*/\s*(\d+)` → **BA/Auftrag** (the number before `/`, e.g. `1024738`) + an ACM sub-position (after `/`, not used for matching).
  - `Bestelldaten\s*(\S+)` → e.g. `4501119979/A350/CCRC/MSN830/6-Bett`. Split on `/`: **PO base** (`4501119979`), **AC programme** (`A350`), **compartment** (`CCRC`|`FCRC`), **MSN** (strip `MSN` → `830`), **bed config** (`6-Bett` → `6`).

Parsing strategy: run `pdftotext -layout` via subprocess, then a line-oriented state machine that opens a new position on the `Pos Artikel Menge ME` line and accumulates the labelled fields until the next position or the footer. Footer/bank-detail lines and page headers are ignored. Collect **warnings** for any field a position is missing.

### ATR template (output frame) — cell map verified in Phase A

Header block fixed cells: `D1` Customer, `F1/G1/I1/J1/K1` PO No (split), `D2` AC Programme, `G2` MSN, `G3` ATA, `D3` Work Package, `D4` Purchaser Spec, `G4` NSCM, `D5` ATP, `D6` Supplier Spec, `D7` Reference No, `D8` Supplier, `G8` Customer Spec, `D9` WO No, `A11` set title, `A12/C12` Weighing date, `F12` Weighing equipment, `I12/L12` Testing date. Table header row 13 (`A` PO Pos, `B` Article Code, `C` Part Number, `D` Part Name, `E` Serial, `F` Drawing No/Issue, `G` Qty, `H` Weight, `I–N` inspection). Parts from row 15; section labels (category) on their own rows in col A; totals block (`Total weight`, `Max. Guaranteed weight`, `Test Results`) located by scanning col F/A for the labels. The **Doc-No** (`ACM-…-ATR-4545-01 / Issue / Date / Page`) lives in the worksheet **print header**, not a cell — set via `ws.oddHeader`.

### Containerbeschriftung (output) — verified docx

Five short lines: `BA {ba_auftrag}` / `PO {po_base}` / `Pos. {comma-joined sorted po_pos}` / `{programme} Teppiche MSN {msn}` / `Container {container_number}`. Generated with `python-docx`.

## Data model

New tables via Alembic `v1_64_atr_delivery` (`down_revision = "v1_63_atr_reference"` — re-verify head at implementation). Models in `backend/app/models/atr.py` (extend the existing module file).

### `atr_delivery`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `source_filename` | String(255) NOT NULL | original Lieferschein filename |
| `lieferschein_nr` | String(40) NULL | parsed |
| `datum` | Date NULL | parsed |
| `ba_auftrag` | String(40) NULL | from `Auftrag Nr.` |
| `po_number` | String(60) NULL | full PO string; prefilled with PO base, operator completes the `79-0830-94` suffix |
| `ac_programme` | String(40) NULL | `A350` |
| `compartment` | String(8) NULL | `CCRC`/`FCRC` |
| `msn` | String(20) NULL | `830` |
| `bed_config` | String(8) NULL | `6`/`8` |
| `set_title` | String(100) NULL | default `SET {bed} BED {compartment}`, editable |
| `atr_number` | String(80) NULL | editable, prefilled (e.g. `ACM-A350CRC-ATR-____-01`) |
| `container_number` | String(40) NULL | entered on review |
| `weighing_date` | Date NULL | default today |
| `testing_date` | Date NULL | default today |
| `qa_signer` | String(100) NULL | default from `atr_template.qa_signer_default` |
| `max_guaranteed_weight_kg` | Numeric(8,3) NULL | editable |
| `status` | String(16) NOT NULL | `draft` / `generated` |
| `atr_xlsx` | BYTEA NULL | last generated ATR workbook (stable re-download) |
| `atr_pdf` | BYTEA NULL | last generated ATR PDF (null if LibreOffice failed) |
| `label_docx` | BYTEA NULL | last generated Containerbeschriftung |
| `created_at` / `updated_at` | DateTime(tz) NOT NULL | |

### `atr_delivery_item`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `delivery_id` | Integer FK → atr_delivery.id `ON DELETE CASCADE` NOT NULL | |
| `pos` | Integer NULL | Lieferschein position |
| `supplier_article_code` | String(40) NULL | from Lieferschein |
| `part_number` | String(60) NULL | `Ihre Nr.` raw |
| `part_number_norm` | String(40) NULL | match key |
| `matched_part_id` | Integer FK → atr_part.id `ON DELETE SET NULL` NULL | |
| `part_name` | String(200) NULL | catalog name (matched) or Lieferschein Bezeichnung (unmatched) |
| `drawing_number_issue` | String(60) NULL | catalog (matched) |
| `category` | String(40) NULL | catalog (matched) |
| `qty` | Integer NOT NULL DEFAULT 1 | |
| `weight_kg` | Numeric(8,3) NULL | default from catalog `default_weight_kg`, editable |
| `po_pos` | String(20) NULL | default from catalog `po_pos`, editable |
| `match_status` | String(12) NOT NULL | `matched` / `unmatched` |
| `row_order` | Integer NOT NULL | preserves Lieferschein order |

## Backend units

- **`services/atr_lieferschein.py`** — `parse_lieferschein(pdf_bytes) -> ParsedLieferschein` (header + ordered positions + warnings). Uses `pdftotext -layout` via subprocess on a temp file. Pure parsing.
- **`services/atr_match.py`** — `match_positions(db, parsed) -> MatchedDelivery`: look up each position's `part_number_norm` in `atr_part`; build delivery header (compartment/bed/set-title from Bestelldaten) + items with matched/unmatched status and catalog-prefilled fields.
- **`services/atr_generate_xlsx.py`** — `build_atr_xlsx(template_bytes, delivery, items) -> bytes`: load the template, fill the header block + print-header Doc-No, clear the template's example part rows in the table region, write delivery items grouped by category (section header rows + part rows, styles copied from a template reference part row), red-fill unmatched rows + a warning note, recompute Total weight, set Max-guaranteed + Test Results. Then `convert_xlsx_to_pdf(xlsx_bytes) -> bytes` via LibreOffice headless (mirror the signage conversion service: temp dir, `soffice --headless --convert-to pdf`, timeout/concurrency guard).
- **`services/atr_generate_docx.py`** — `build_containerbeschriftung(delivery, items) -> bytes` via `python-docx`.
- **`routers/atr_delivery.py`** — admin-gated (router-level `get_current_user` + `require_admin`), `prefix="/api/atr/deliveries"`:
  | Method | Path | Purpose |
  |--------|------|---------|
  | POST | `/upload` | multipart PDF → parse + match → create draft delivery → return delivery + items |
  | GET | `/input-files` | list `*.pdf` in `ATR_INPUT_DIR` (404/empty if unset) |
  | POST | `/input-files/process` | `{filename}` from `ATR_INPUT_DIR` → parse + match → draft |
  | GET | `` | list deliveries |
  | GET | `/{id}` | delivery + items |
  | PATCH | `/{id}` | edit delivery header fields |
  | PATCH | `/{id}/items/{item_id}` | edit a line (weight, po_pos) |
  | POST | `/{id}/generate` | build all three files, set status=`generated`, return a manifest (filenames + which were red-flagged) |
  | GET | `/{id}/files/{kind}` | download `atr_xlsx` / `atr_pdf` / `label_docx` (kind enum) |

  Generated bytes are stored on the delivery (or regenerated on download) — store `atr_xlsx`/`atr_pdf`/`label_docx` as BYTEA columns on `atr_delivery` (added in the same migration) so downloads are stable and re-download works without re-running LibreOffice. Schemas in `backend/app/schemas/atr_delivery.py`.

## Frontend

Under the existing `/atr` area:
- `/atr/deliveries` — list (source file, BA, status, created) + an "Upload Lieferschein" control and, when `ATR_INPUT_DIR` is set, an "From input folder" picker.
- `/atr/deliveries/:id` — review page: editable header card (ATR no, container no, set-title, PO, dates, QA signer, max-guaranteed) + a line-item table (weight + po_pos editable; unmatched rows visually flagged) + a **Generate** button → then download buttons for the `.xlsx`, `.pdf`, `.docx`.
- Launcher tile already routes to `/atr`; add a sub-nav/link to Deliveries. German + English i18n (flat `atr.deliveries.*` keys — the project uses `keySeparator: false`).
- `atrApi.ts` extended with delivery types + fetchers (Decimals as strings).

## Error handling

- Parser collects warnings (missing fields, unparsable position) rather than throwing; a Lieferschein with zero parsable positions → 422 with a clear message.
- Non-PDF upload, or `pdftotext` failure → 400.
- `input-files` when `ATR_INPUT_DIR` unset or path missing → empty list + a flag (not a 500); path-traversal guarded (only basenames within the dir).
- LibreOffice conversion failure or timeout → the xlsx + docx still generate and download; the PDF is marked unavailable with an error (don't lose the whole generation over the PDF step).
- Unmatched items: never an error — red fill + warning in the xlsx, surfaced in the generate manifest.
- All admin-gated (CI `test_admin_gate_audit.py`).

## Testing

Backend (pytest, against the disposable `acm_test` DB; **never** production `acm_kpi`):
- `test_atr_lieferschein.py` — parse a committed text fixture (the `pdftotext -layout` output of the sample, stored under `backend/tests/fixtures/atr/`): asserts header fields + all 8 positions with article/part-number/index/BA/Bestelldaten breakdown + warnings on a malformed block.
- `test_atr_match.py` — matched vs unmatched classification, compartment/bed/set-title derivation, catalog prefilling (weight/po_pos/drawing).
- `test_atr_generate_xlsx.py` — build from a fixture template + a small delivery: header cells filled, part rows written with category grouping, unmatched row carries the red fill, Total weight = sum; re-open the produced xlsx with openpyxl to assert.
- `test_atr_generate_docx.py` — the five label lines correct (re-open with python-docx).
- `test_atr_delivery_router.py` — upload→draft, patch header/item, generate→manifest, download each kind, admin-gate.
- PDF conversion: one smoke test that `convert_xlsx_to_pdf` returns non-empty `%PDF` bytes (skippable/marked if `soffice` unavailable, mirroring the signage conversion test).

Frontend: a review-page render test (header fields + line items, unmatched flagged) mirroring the Phase A page tests (I18nextProvider + QueryClient).

**Acceptance check (manual):** upload the real `LIEFERSCHEIN_10005_20189798.pdf`, import the 12 reference workbooks first (Phase A), review, generate — confirm the ATR lists the 8 carpet parts with the expected drawing numbers + a plausible total, and the label matches the example (`BA 1024738 / PO 4501119979 / Pos. 050,300,340,350,360,390,400,410 / A350 Teppiche MSN 830 / Container …`).

## Open items (carried)

1. **PO suffix** (`79-0830-94`) and **PO-Pos values** (`050,300,…`) are not in the Lieferschein or templates — they come from the Diehl PO. Phase B prefills PO base from Bestelldaten and PO-Pos from the catalog `po_pos` field (operator-maintained in Phase A); both remain editable on review. A future enhancement could ingest the Diehl PO directly.
2. **Max-guaranteed weight** varies by 6/8-bed; Phase B makes it an editable delivery field (no per-config store yet).
3. **Output-dir write + scheduler automation** → Phase C.

## Roadmap context

```
Phase A (done)       Reference foundation: catalog + template + import UI
Phase B (this spec)  Generate from a Lieferschein (manual): parse → match → review → ATR(.xlsx+PDF) + label(.docx) → download
Phase C              Fileserver + automation: SMB/AD mount, settings page, scheduler scan, write-to-Output, archive
```

## Implementation waves (for the plan)

1. **Ingest + match + persist:** migration + models + schemas; `atr_lieferschein` parser; `atr_match`; upload/input-files/list/get/patch delivery router; tests. Deliverable: upload a Lieferschein → reviewable draft delivery (no generation yet).
2. **Generation:** `atr_generate_xlsx` (+ LibreOffice PDF), `atr_generate_docx`, `libreoffice-calc` + `python-docx` infra, generate/download endpoints; tests. Deliverable: generate + download the three files.
3. **Review UI:** deliveries list + review page + generate/download, `atrApi` + i18n; tests.
