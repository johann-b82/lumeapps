# Finance Dashboard

The finance perspective shows how much of your revenue goes to material and personnel. A toggle at the top switches between the two metrics **Material** and **Personnel**. Each view has the same structure: four KPI cards on top, a history bar chart below, and a verification table underneath. Everything can be filtered by period.

You reach the perspective via the **Finance** tile in the KPI dashboard (route `/finance`).

## Switching Material and Personnel

The toggle at the top (**Material** / **Personnel**) determines which metric you see. Both views share the same period — switching views keeps the selected date range.

## Material Cost Ratio

**Material cost ratio = material cost / revenue.** Material cost is the consumed quantity per article multiplied by the most recent goods-receipt price (GR price); revenue is net revenue (RG/GS). Lower is better.

Four cards:

- **Material Cost Ratio** (%) — the ratio itself, with delta badges vs. the previous period and previous year once a comparison range is available. Badges are coloured by the sign of the change.
- **Material Cost** (€) — the numerator.
- **Revenue** (€) — the denominator.
- **No Price** (count) — consumed articles without a GR price. They are excluded from material cost and surfaced here for transparency.

### History and configurable target line

The bar chart shows the material cost ratio per period. The **−** / **+** buttons at the top right change the granularity (week / month / quarter / year); the from/to fields let you pick a custom range.

If a target value is set in Settings, a dashed **target line** appears (e.g. `Target 15.0 %`). You set the value under **Settings → Finance → Material cost ratio** (in percent). An empty field hides the line.

### Verification table "Material consumption per article"

One row per consumed article in the period. Columns: Article No., Description, Consumed Qty, Unit Price (the GR price used) and Material Cost. The table is searchable, sortable by column headers, and paginated. Articles without a GR price appear muted with "—" — they don't count toward the material cost total.

## Personnel Cost Ratio

**Personnel cost ratio = personnel cost / revenue.** Personnel cost is the gross salary cost from Personio (fixed salaries prorated day-by-day, hourly wages over recorded working time); revenue is the same net revenue as above. Lower is better.

Four cards: **Personnel Cost Ratio** (%, with the same delta badges), **Personnel Cost** (€, numerator), **Revenue** (€, denominator) and **Employees** (count of employees with cost in the period).

Here too the bar chart shows the history with granularity buttons and from/to fields. You set the target line under **Settings → Finance → Personnel cost ratio**.

The verification table **Personnel cost per department** aggregates per department — columns: Department, Employees, Personnel Cost. Individual salaries are never shown.

## Feeding data

The material cost ratio draws on uploaded exports (stock movements, material prices/goods receipt) and revenue; the personnel cost ratio uses Personio data (like the HR dashboard) plus revenue. For upload instructions see [Uploading data](/docs/user-guide/uploading-data). Period presets and custom ranges are explained under [Filters &amp; periods](/docs/user-guide/filters).
