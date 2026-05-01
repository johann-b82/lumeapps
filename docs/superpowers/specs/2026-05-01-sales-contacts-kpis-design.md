# Sales Contacts KPIs — Design

**Status:** Draft for review
**Date:** 2026-05-01
**Author:** Johann + Claude

## Goal

Add four new sales-activity KPIs (Erstkontakte, Interessenten, Visits, Angebote) and one combined Orders/customer-concentration card to the Sales Dashboard, all sliced by week and broken down per sales employee. Sales employees are identified through a new Personio sales-department mapping (mirroring the existing production-department config).

## Inputs

### New file: Kontakte (sales contact log)

Source file: `OneDrive_1_30/20260430_Kontakte.txt` (sample). Encoding ISO-8859-1, CRLF, tab-separated, 29 columns wrapped in `="…"` per Excel-export idiom.

Columns we use (all others ignored on ingest, but stored raw for debuggability):

| Source column | Stored as | Type | Note |
|---|---|---|---|
| `Datum` | `contact_date` | date | DD.MM.YYYY → `date` |
| `Wer` | `employee_token` | text | Uppercased surname, e.g. `GUENDEL`, `KARRER`. Used to bind to a Personio employee. |
| `Typ` | `contact_type` | text | One of `EMAIL`, `MESSE`, `TEL`, `ERS`, `ORT`, `ANFR`, `EPA`, `REFURB`, `ONL`, blank — drives the KPI buckets. |
| `Gruppe` | `customer_group` | text | E.g. `AL`, `OEM`, `MRO` — kept for future filters. |
| `Sta` | `status` | smallint | 0 / 1. We only count rows with `status = 1` toward KPIs (avoids draft/cancelled entries). |
| `Name` | `customer_name` | text | For tooltips / debugging. |
| `Kommentar` | `comment` | text | First word checked for `"Angebot"` prefix to drive the Angebote KPI. |
| `VrgID` | `external_id` | text | Source-system ID; non-null but not unique on its own. |

Upload rules:
- Re-using the existing Aufträge upload pattern (FastAPI multipart endpoint, idempotent replace-by-date-range).
- Detection: a new dedicated endpoint `POST /api/uploads/contacts` (we do not auto-detect by header — admins pick the upload type, same as today).
- Replace semantics: any row whose `contact_date` falls inside `[min(file.date), max(file.date)]` is deleted, then the file's rows are inserted. Same as how Aufträge import works.

### KPI rules (all on `status = 1` only)

| KPI | Rule |
|---|---|
| Erstkontakte | `contact_type = 'ERS'` |
| Interessenten | `contact_type IN ('ANFR', 'EPA')` |
| Visits | `contact_type = 'ORT'` |
| Angebote | `comment ILIKE 'Angebot%'` |

Weekly aggregation: ISO week (Monday-start), grouped by `(iso_year, iso_week, employee_id)`. Rows whose `employee_token` cannot be mapped to a Personio employee are surfaced in the import report (count + sample tokens) and **excluded** from the chart.

### Sales-employee binding (Personio)

New Personio config: `sales_department_keys` — same shape as the existing `production_department_keys`. Lives on the **Settings → HR** page, in the Personio section, directly below the production-department picker.

Resolution rule, per Personio sync tick:

1. Pull all employees in `Personio.employments[*].department.id IN sales_department_keys`.
2. For each, derive `employee_token = uppercase(last_name)` with German umlaut folding (Ä→AE, Ö→OE, Ü→UE, ß→SS) and removal of non-alpha characters.
3. Persist this mapping in a new `sales_employee_aliases` table: `(personio_employee_id, employee_token)`. One canonical token per employee, but the table allows additional tokens (manual overrides — see below).
4. Surface tokens that appear in `sales_contacts` but cannot be mapped, on a new "Unmapped sales reps" subsection of the HR settings page (count + the 5 most-recent date examples).
5. Admin can add a manual alias `(personio_employee_id, employee_token)` row from that subsection — that fixes nicknames like `GUENNI` (an existing token in the file).

**Edge cases we accept:**
- A single Personio employee may legitimately have multiple aliases (`SCHMIDT_J`, `JSCHMIDT`, etc.). The table is many-to-one (alias → employee).
- A sales employee who leaves Personio: their existing contact-log rows remain attributed to them historically. We do not retroactively rewrite history.

## Output (UI)

### Sales Dashboard — new section "Vertriebsaktivität"

Below the existing revenue cards. One Card containing four equal-width line charts (responsive: 2×2 on md, 1×4 stacked on sm), then a second Card with the combined Orders metric.

#### Charts (4×)

Each chart is a Recharts `LineChart`:
- X-axis: ISO week label (e.g. `KW 14 / 2026`) for the selected date range.
- Y-axis: integer count.
- One line per sales employee, color from a stable palette indexed by `personio_employee_id` (so the same employee gets the same color across all four charts).
- Tooltip: shows total + per-employee values for the hovered week.
- Empty state: "Keine Vertriebsaktivität in diesem Zeitraum" placeholder when the selected range yields zero rows.

Date range: the existing Sales Dashboard date-range filter applies to all four charts and the combo card.

#### Combo card "Auftragsverteilung" (Orders distribution)

Single Card with three KPI tiles (re-use existing `KpiCard` component):

| Tile | Value | Note |
|---|---|---|
| Aufträge / Woche / Vertriebler | mean of (orders count) / (number of weeks in range) / (number of mapped sales employees) | Personio sales employees only. |
| Top-3-Kunden Anteil | sum(top-3 customers' Auftragsvolumen) / sum(all Auftragsvolumen) × 100 | "Top 3" by total Auftragsvolumen in the selected range. |
| Restkunden Anteil | 100 % − Top-3-Kunden Anteil | Belt-and-suspenders: also computed server-side, not in JS. |

## Backend

### Schema (Alembic migration)

```sql
-- new
CREATE TABLE sales_contacts (
    id BIGSERIAL PRIMARY KEY,
    contact_date DATE NOT NULL,
    employee_token TEXT NOT NULL,
    contact_type TEXT,
    customer_group TEXT,
    status SMALLINT NOT NULL,
    customer_name TEXT,
    comment TEXT,
    external_id TEXT,
    raw JSONB,                          -- the rest of the row, for re-derivation later
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT sales_contacts_status_check CHECK (status IN (0, 1))
);
CREATE INDEX sales_contacts_date_idx ON sales_contacts(contact_date);
CREATE INDEX sales_contacts_token_idx ON sales_contacts(employee_token);

CREATE TABLE sales_employee_aliases (
    id BIGSERIAL PRIMARY KEY,
    personio_employee_id BIGINT NOT NULL REFERENCES personio_employees(id) ON DELETE CASCADE,
    employee_token TEXT NOT NULL UNIQUE,    -- the alias is unique; one alias maps to one employee
    is_canonical BOOLEAN NOT NULL DEFAULT FALSE  -- the auto-derived token from last_name
);
CREATE INDEX sales_employee_aliases_employee_idx ON sales_employee_aliases(personio_employee_id);
```

Settings table gets one new key (Pydantic-validated): `personio_sales_department_keys: list[str]`. Same allowlist treatment as the existing production-department key.

### Routes

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/api/uploads/contacts` | admin | Multipart Kontakte file upload + replace-by-range insert. Returns `{rows_inserted, unmapped_tokens: [{token, count}], date_range}`. |
| GET | `/api/data/sales/contacts-weekly` | viewer | Returns `{weeks: [{iso_year, iso_week, label, per_employee: {personio_employee_id: {erstkontakte, interessenten, visits, angebote}}}]}` for the selected `from`/`to` query params. One round trip drives all 4 charts. |
| GET | `/api/data/sales/orders-distribution` | viewer | Returns `{orders_per_week_per_rep, top3_share_pct, remaining_share_pct}` for the same `from`/`to`. Drives the combo card. |
| POST | `/api/admin/sales-aliases` | admin | Manual alias creation: `{personio_employee_id, employee_token}`. |
| DELETE | `/api/admin/sales-aliases/{id}` | admin | Remove a manual alias (canonical aliases are protected — sync owns them). |

The two GET endpoints take `from` and `to` (ISO date) query params; defaults to "last 12 weeks" when omitted, mirroring the existing Sales Dashboard endpoints.

### Personio sync changes

The existing periodic Personio sync gets one extra step at the end: rebuild canonical sales aliases (`is_canonical = TRUE` rows). Manual aliases (`is_canonical = FALSE`) are never touched by the sync.

## Frontend

### Upload page

Add a new "Kontakte" radio next to "Aufträge" in the upload type picker. POSTs to `/api/uploads/contacts`. Result toast shows `rows_inserted` and (if any) `unmapped_tokens` count + a "Manage aliases" link to `/settings/hr#sales-aliases`.

### HR settings page

Below the existing Personio production-department picker, add:

1. **Sales-Abteilungen** picker (multi-select, same UX as production departments).
2. **Unmapped sales reps** subsection: a small table with columns `Token`, `Vorkommen`, `Letzter Kontakt`, `Aktion → Zuordnen`. Clicking "Zuordnen" opens a dialog that lets the admin pick a Personio sales employee to alias to.
3. **Manuelle Aliasse** subsection: list of `(token → employee)` rows with a delete button. Canonical aliases shown read-only with a 🔒 icon.

### Sales Dashboard

After the existing revenue chart and revenue cards, add:

1. New Card "**Vertriebsaktivität**" — 2×2 grid of `LineChart`s (Erstkontakte, Interessenten, Visits, Angebote). Single TanStack Query fetch on `/api/data/sales/contacts-weekly`.
2. New Card "**Auftragsverteilung**" — three KPI tiles. Single fetch on `/api/data/sales/orders-distribution`.

Both cards inherit the dashboard's existing date-range filter via the same query-key pattern as the revenue cards.

### Color palette

Reuse the existing `sensorPalette` constant from the Sensors chart for the per-employee line colors, so visual language stays consistent across the app. Color is keyed by `personio_employee_id` (stable across charts and across page reloads).

## Tests

- **Backend (pytest)**:
  - `test_contacts_upload_idempotent` — same file uploaded twice yields the same rows count, not duplicates.
  - `test_contacts_iso_week_aggregation` — synthetic rows across week boundary land in the correct ISO week.
  - `test_kpi_rules_match_spec` — one fixture row per KPI bucket, verify the right rule fires.
  - `test_unmapped_token_reporting` — uploads a fixture row whose `Wer` token is unknown; expects it surfaced in the response.
  - `test_alias_resolution` — manual alias overrides canonical; multiple aliases for one employee resolve.
  - `test_top3_remaining_share_pct` — synthetic 5-customer dataset, expect exact percentages.

- **Frontend (vitest)**:
  - `useContactsWeekly.test` — query-key shape, refetch on date-range change.
  - `SalesActivityCard.test` — given a 3-rep, 4-week fixture, four lines render with stable colors.
  - `OrdersDistributionCard.test` — three-tile rendering and the rounding rule (sum to 100 ± 0.1).
  - `KontakteUpload.test` — upload form posts to the right endpoint, surfaces unmapped-token toast.

## Out of scope (explicit non-goals)

- No retroactive cleanup of historical contacts when an alias is added — counts are recomputed from raw data on every read.
- No edit-in-place for individual contact rows. Re-upload the corrected file.
- No drill-down from a chart line into the raw contacts list (could come later).
- No alerting on KPI thresholds (e.g. "warn if Visits/week per rep < 2"). Future feature.

## Open questions

1. **Date range default for the new charts** — match the existing revenue chart default (last 12 weeks) or pick something else (e.g. YTD)?
2. **Inactive sales employees** (left the company, but had contacts in the past) — show as a faded line, or hide from the legend? Default proposal: show, but with a `(inaktiv)` suffix in the legend.
3. **Color stability when employee count is high** — the existing `sensorPalette` has 8 colors. With 12+ active sales reps, lines start sharing colors. Acceptable, or do we want a larger palette?

## File-touch budget (rough estimate)

- **Backend (~12 files):** 1 Alembic migration; 2 new SQLAlchemy models; 4 new Pydantic schemas; 2 new routers (uploads/contacts, data/sales-extras); 1 service module for week aggregation + alias resolution; 1 settings-key addition; 1 personio-sync hook; existing tests touched for fixture additions.
- **Frontend (~10 files):** 1 new upload form variant; 1 SalesActivityCard component (with 4 inner LineChart subs); 1 OrdersDistributionCard; 1 useContactsWeekly + 1 useOrdersDistribution hook; HR settings page extension (sales-departments picker + aliases subsection); 1 toast variant; locale additions.

## Migration / rollout

- Ship behind no flag — internal tool, single tenant. The new charts are inert until a Kontakte file is uploaded (empty-state placeholder). The combo card is inert until at least one Personio sales-department key is set.
- README v1.41 entry summarizing the four new KPIs and the new HR settings option.
