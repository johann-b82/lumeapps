# Procurement Dashboard

The Procurement perspective shows how reliably your suppliers deliver on time. The first section, **On-Time Delivery (OTD)**, combines four KPI cards at the top, an OTD trend bar chart below, and a verification table listing every delivery position in the period. Everything is filterable by date range.

You reach the perspective via the **Procurement** tile in the KPI dashboard (route `/procurement`) or via the section switcher in the page header. Further sections (On Quality – Workbenches, Material Suppliers) are planned and will dock on here later.

## What counts as "on time"?

Scoring is per **delivery position** – not by quantity. A position counts as **on time** when its delay (`delay in days`) is zero or negative, i.e. delivered on or before the confirmed target date (early also counts as on time). The date filter uses the **actual delivery date** (goods receipt), so the OTD rate matches the same window as the other KPIs.

The OTD rate is the share of on-time positions among all positions in the period. **Higher is better** – the opposite polarity of the complaint rate.

## KPI cards

- **OTD rate** – share of positions delivered on time. Shows delta badges vs. previous period and previous year once a comparison window is available. Because a **high** rate is good, an improvement is shown in green.
- **On-time positions** – number of on-time positions (the numerator of the rate).
- **Total positions** – number of all positions in the period (the denominator).
- **Avg. delay** – average lateness in days across the period's positions.

## OTD rate over time

The bar chart shows the OTD rate per time bucket. The **−** / **+** buttons top right switch the granularity (week / month / quarter / year); the default is picked automatically from the selected range. The from/to fields in the chart header let you set a custom range directly – cards, chart and table stay in sync.

A dashed **target line** marks the fixed goal of `98.0%`. Bars below the line miss the target.

## Verification table

The table lists one row per delivery position in the period. It is searchable via the search box (order, supplier, address no., article number, article name), sortable via the column headers, and paginated (50 rows per page). The delay column is colour-coded: ≤ 0 days on time (green), &gt; 0 days late (red).

| Column | Description |
|--------|-------------|
| Order | Order number of the position |
| Supplier | Supplier name (with address no. in brackets) |
| Article | Article name or article number |
| Delivered | Actual delivery date (goods receipt) |
| Target | Confirmed target date |
| Delay | Delay in days (+ late, − early) |
| Quantity | Delivered quantity |

## Loading data

The perspective is fed by a delivery-reliability export that you load via the upload page. It provides the actual delivery date, target date and delay for each delivery position.

For instructions on uploading, see [Upload data](/docs/user-guide/uploading-data). Date-range presets and custom ranges are explained under [Filters &amp; date ranges](/docs/user-guide/filters).
