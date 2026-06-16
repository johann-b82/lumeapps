# Einkauf — Liefertermintreue / OTD (On-Time Delivery)

**Date:** 2026-06-16
**Status:** Approved (design), pending implementation plan

## Context

LumeApps groups KPIs into top-level *areas* (Sales, HR, Quality, Sensors). Each
area follows the same vertical slice: file ingest (parser → admin upload
endpoint → table) + aggregation service + viewer-gated KPI endpoints + a
frontend section (KPI cards, history chart, verification table) + an upload
drop-zone.

A new **Einkauf** (procurement) area is planned with three sections:

1. On Quality – Werkbänke
2. On Quality – Material Lieferanten
3. **Liefertermintreue / OTD** ← *this spec*

Only the OTD section is built now. The Einkauf area scaffolding (launcher tile,
`/procurement` route, page shell, `/api/procurement` router) is created so the
two later sections dock on as additional views (toggle pattern, like
`QualityPage`'s audits/complaints toggle). The other two sections are **out of
scope** here.

## Goal

Upload the `dev_excel_Liefertreue_Einkauf.txt` export and see the supplier
on-time-delivery rate (OTD) on the Einkauf dashboard, consistent with the
existing KPI cards/chart/table and the global month/quarter date selector.

## Data source

`dev_excel_Liefertreue_Einkauf.txt` — tab-separated, Windows-1252 encoding,
German number/date formats.

- **Row 1** — report title carrying the evaluation period, e.g.
  `Auswertung:	Liefertreue (von 01.01.2026 bis 30.04.2026)`. Parsed for the
  `von … bis …` range; stored as batch metadata and shown as the data-coverage
  hint / default window. Parser skips this row.
- **Row 2** — column header.
- **Row 3+** — one row per supplier delivery position.

Relevant columns:

| Column | Meaning | Use |
|---|---|---|
| `Auftrag`, `Pos`, `UPos` | order line identity | composite upsert key |
| `Kundennummer` | supplier address number (e.g. `81105`) | `adr_nr` (cross-links to other Einkauf data) |
| `Kunde` | supplier name | display |
| `geliefert` | actual goods-receipt date (e.g. `05.01.2026`) | **time-window filter** |
| `Lieferdatum` | confirmed target date | stored, display |
| `Verzug (Tage)` | delay in days (e.g. `47`) | **on-time classifier** |
| `Menge`, `ME` | quantity / unit | stored, display |
| `Artikel`, `Bezeichnung` | article no. / name | display |

## Formula (confirmed)

OTD is **count-based** over positions, classified by `Verzug (Tage)`:

```
pünktlich = count(positions with Verzug ≤ 0)   within [first, last] on `geliefert`
gesamt    = count(all positions)               within [first, last] on `geliefert`
OTD-Rate  = pünktlich / gesamt          (fraction 0..1, frontend renders × 100 %)
```

- **On time** = `Verzug ≤ 0` (on or before target; early deliveries count as
  on time).
- **Basis** = position count (not quantity).
- **Time window** = `geliefert` date — keeps OTD consistent with the existing
  date-range selector and history chart. The row-1 Auswertung period is parsed
  for context/default, not used as the aggregation filter.
- Rate stored as a **fraction**, matching `complaint_rate` so the frontend
  reuses the locale-aware `Intl.NumberFormat` percent path.
- **Direction:** higher OTD is *better* (opposite of complaint rate). Delta
  badges must treat a positive change as favourable.

Returned alongside the rate: `punctual_count`, `total_count`, `avg_delay`
(mean `Verzug` over the window), plus `previous_period` / `previous_year`
baseline rates (reusing `prior_window_same_length` / `same_window_prior_year`
from `hr_kpi_aggregation`).

## Architecture

### Data model (Variant: dedicated ingest table)

New table **`delivery_reliability`** — one row per delivery position.

- Upsert key: `(auftrag, pos, upos)` → `uq_delivery_reliability_auftrag_pos`
  (`ON CONFLICT DO UPDATE`, idempotent re-upload), mirroring
  `delivery_records`.
- Typed columns: `adr_nr` (String), `supplier_name` (String),
  `delivered_date` (Date, indexed — every query filters it), `target_date`
  (Date), `verzug_tage` (Integer, indexed — the classifier), `quantity`
  (Numeric(15,3)), `unit` (String), `article_number` (String),
  `article_name` (String).
- `raw` (JSONB) — full source row for auditing.
- `upload_batch_id` FK → `upload_batches.id` (`ondelete=CASCADE`).
- Index `ix_delivery_reliability_delivered_date` on `delivered_date`.

`upload_batches.kind` check constraint extended to permit
`'delivery_reliability'` (current set:
`orders, contacts, quality, interessenten, offers, revenues, auftraege,
deliveries`).

Migration: **`v1_60_procurement_otd`**, `down_revision = "v1_59_quality_quantity"`.

ORM class `DeliveryReliabilityRecord` added to `app/models/_base.py` and
re-exported from `app/models/__init__.py` (required for Alembic registration).

### Backend

- **Parser** `app/parsing/delivery_reliability_parser.py`
  - Signature `parse_delivery_reliability_file(contents, filename) ->
    (rows, errors, period)` where `period = (von, bis) | None` parsed from
    row 1.
  - Tab-separated read with `skiprows` to land the header on row 2; German
    date `TT.MM.JJJJ` and decimal `55,3` handled with the same helpers as
    `delivery_parser`. `Verzug` parsed as signed int (may be negative).
  - Dedupe `(auftrag, pos, upos)` within a file; mandatory-field validation
    returns `(row, column, message)` error dicts.
- **Upload endpoint** (admin) `POST /api/upload-delivery-reliability` in
  `app/routers/uploads.py` — composite-key chunked upsert, returns
  `DeliveryReliabilityUploadResponse {rows_inserted, rows_updated, period,
  errors}`. Empty/failed files logged as a batch, mirroring
  `upload_deliveries`.
- **Aggregation service** `app/services/otd_aggregation.py`
  - `_counts_for_window(db, first, last) -> (punctual, total, delay_sum)` —
    SQL `COUNT(*)` with `verzug_tage <= 0` for the punctual count, filtered on
    `delivered_date`.
  - `compute_otd(db, first, last) -> {rate, punctual_count, total_count,
    avg_delay, previous_period, previous_year}`.
  - `compute_otd_history(db, buckets) -> [{month, rate, punctual_count,
    total_count}]` — reuses the same `_bucket_windows` granularity util the
    complaint-rate history uses.
  - `list_otd(db, first, last, *, limit=500) -> [DeliveryReliabilityRecord]`
    for the verification table, ordered by `delivered_date desc`.
- **KPI router** `app/routers/procurement_kpis.py`, prefix `/api/procurement`,
  `dependencies=[Depends(get_current_user)]` (viewer gate). Endpoints:
  - `GET /otd` → `OtdValue`
  - `GET /otd/history` → `list[OtdHistoryPoint]` (`granularity` query param)
  - `GET /otd/list` → `list[OtdRow]`
  - Default window when none supplied: current month bounds (same helper the
    quality router uses).
- **Schemas** in `app/schemas/_base.py`: `DeliveryReliabilityUploadResponse`,
  `OtdValue`, `OtdHistoryPoint`, `OtdRow`.
- **Register** `procurement_kpis_router` in `app/main.py`.

### Frontend

- **Page** `pages/ProcurementPage.tsx` + route `/procurement` in `App.tsx` +
  tile "Einkauf" on `LauncherPage.tsx`. Page is built with a section
  toggle/container (single "Liefertermintreue / OTD" segment for now) so
  Werkbänke / Material-Lieferanten dock on later.
- **Section components** under `components/dashboard/`:
  - `OtdCardGrid` — cards: OTD-Quote %, pünktliche Positionen, Gesamt-Positionen,
    Ø Verzug (Tage). Delta badges with *higher-is-better* polarity.
  - `OtdChart` — history line/bar with the existing granularity zoom control.
  - `OtdTable` — verification table of positions (supplier, geliefert,
    Lieferdatum, Verzug, Menge), sortable.
- **Upload** `components/DeliveryReliabilityDropZone.tsx` on `UploadPage.tsx` —
  `react-dropzone` + `useMutation(uploadDeliveryReliabilityFile)`, toast
  summary, invalidates `procurementKeys.all` + `["uploads"]`. Accepts `.txt`.
- **API/query wiring**: `lib/api.ts` (`uploadDeliveryReliabilityFile`,
  `fetchOtd`, `fetchOtdHistory`, `fetchOtdList` + types); `lib/queryKeys.ts`
  (`procurementKeys` factory).
- **i18n**: `locales/de.json` + `locales/en.json` (section title, card labels,
  upload strings, `kind_delivery_reliability`).

## Non-goals

- Werkbänke and Material-Lieferanten sections (later, reuse this scaffolding).
- Ingest of `AswKpf_WE.txt` / `dev_excel_LIE.txt` (those feed the other two
  sections, not OTD).
- Any change to `quality_records` / 8D data.

## Verification (success criteria)

1. **Parser tests** (`tests/test_delivery_reliability_parser.py`): parses the
   sample file (row-1 period extracted, header on row 2, the one data row
   typed correctly incl. negative-capable `Verzug`); German date/decimal;
   blank-line tolerance; missing-column and duplicate-key error paths.
2. **Aggregation test** (`tests/test_otd_endpoint.py`): on a fixture with a
   mix of `Verzug ≤ 0` and `> 0` rows, `compute_otd` returns the correct
   `punctual/total` rate, `avg_delay`, and a `None` rate when the window is
   empty; history buckets split correctly by `delivered_date`.
3. **Endpoint smoke**: `/api/procurement/otd` for the sample period returns a
   plausible rate; `/otd/list` returns the position rows; admin gate on
   upload, viewer gate on reads.
4. **Frontend**: Einkauf tile → page renders the OTD section; upload drop-zone
   ingests the file and the cards/chart populate.

## Reference pattern

This is the same vertical slice as commit `024cb31`
("delivery (LS) ingest + customer-complaint rate dashboard"). Closest analogs
to copy:

- `backend/app/parsing/delivery_parser.py` → reliability parser
- `backend/app/routers/uploads.py::upload_deliveries` → upload endpoint
- `backend/app/services/complaint_rate_aggregation.py` → OTD aggregation
  (counts instead of quantity sums)
- `backend/app/routers/quality_kpis.py` → procurement KPI router
- `backend/alembic/versions/v1_58_delivery_schema.py` → migration
- `frontend/src/components/dashboard/ComplaintRateCardGrid.tsx` /
  `ComplaintRateChart.tsx` / `CustomerComplaintsTable.tsx` → OTD section
- `frontend/src/components/DeliveriesDropZone.tsx` → reliability drop-zone
