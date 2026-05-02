# Sales Dashboard

The Sales Dashboard gives you a real-time view of your sales performance. It combines six summary tiles at the top (three revenue KPIs, then orders / week / rep + a top-3 customer share widget), a "Revenue over time" chart, weekly sales-activity bar charts per rep, and a searchable orders table — all filterable by date range. This article explains each element and how to read the data.

## KPI Cards

At the top of the dashboard, three cards summarise your key metrics for the selected period:

- **Order value** — The sum of all order values in the selected period, displayed in EUR. (Renamed from "Total revenue" / "Gesamtumsatz".)
- **Average order value** — Order value divided by the number of orders, in EUR.
- **Total orders** — The count of all orders in the selected period.

> **Note:** Orders with a value of €0 are excluded from every Sales Dashboard calculation — the three KPI cards above, **Orders / week / rep**, and the **Customer share** bar.

### Delta Badges

Each card shows one or two delta badges that compare the current period to a reference period:

- **This month** — Two badges: vs. the prior month and vs. the same month in the prior year.
- **This quarter** — Two badges: vs. the prior quarter and vs. the prior year.
- **This year** — A single badge vs. the prior year (year-to-date comparison).
- **All time** / **Custom range** — No delta badges.

If no comparison data is available, the badge shows a "No comparison period available" tooltip.

## Order Distribution Row

Directly below the three top KPI cards, a second row breaks the orders down per rep and per customer.

### Orders / week / rep

The mean number of orders per sales rep per week in the selected range. The numerator is the count of non-zero orders. The denominator is the number of distinct creators (derived from the Kontakte file — see "Sales Activity" below) multiplied by the number of weeks in the range. If no Kontakte file has been uploaded yet, this tile reads `0,0`.

### Customer share + Top-3 list

A horizontal stacked bar shows what share of order value the top-3 customers represent versus the rest. Each segment is labelled with its percentage (segments smaller than 8 % hide the inline label to avoid overflow). A small legend below the bar repeats the colour key.

To the right (or below on narrow viewports), a numbered list (1. / 2. / 3.) names the top-3 customers in descending order of value.

The widget uses the primary colour token (`var(--primary)`) for the top-3 segment and the muted surface token (`var(--muted)`) for the rest. If the primary colour is changed in settings, the top-3 segment follows automatically. No red is used anywhere on the Sales Dashboard.

## Revenue over Time Chart

Below the order-distribution row, the **Revenue over time** chart visualises revenue across the selected period.

- Use the **Bar** / **Area** toggle in the top-right corner of the chart to switch the chart type. Bar is the default.
- When a preset with a prior period is selected (This month, This quarter, This year), a comparison series is overlaid on the chart.
- The x-axis uses calendar week labels for the "This month" preset and month + year labels for other presets.

For a full explanation of date presets, custom ranges, and the chart type toggle, see [Filters & Date Ranges](/docs/user-guide/filters).

## Date Range Filter

The date range filter sits at the top of the dashboard page. Select one of four presets:

| Preset | What it shows |
|--------|---------------|
| This month | Orders in the current calendar month |
| This quarter | Orders in the current calendar quarter |
| This year | Orders since 1 January of the current year |
| All time | All orders in the database |

The default selection is **This month**. Your selection resets to the default when you navigate away from the dashboard.

## Sales Activity

Below the revenue chart, the **Sales activity** card shows four weekly **bar charts** — one per KPI. Each bar represents the team total for that week in the primary colour. On hover (the bar switches to the muted colour) a tooltip shows the total plus the per-rep breakdown.

| KPI | What it counts |
|-----|----------------|
| First contacts | New leads (Typ = ERS in the Kontakte file) |
| Prospects | Inquiries that look like an early sales conversation (Typ ∈ {ANFR, EPA}) |
| Visits | On-site customer visits (Typ = ORT) |
| Quotes | Quotes recorded against a contact (any row whose comment starts with "Angebot") |

Sales reps are taken straight from the `Wer` column in the uploaded Kontakte file (e.g. `KARRER`, `GUENDEL`). No Personio mapping is involved.

All four charts respect the dashboard's date-range filter. Week labels are shown without the year (e.g. `KW 18` / `CW 18`).

The charts stay empty until at least one Kontakte file has been uploaded.

## Orders Table

Below the activity charts, the **Orders** table lists every order in the selected date range. You can:

- **Search** — Type in the search box to filter by Order #, Customer, or Project name.
- **Sort** — Click any column header to sort.

Table columns:

| Column | Description |
|--------|-------------|
| Order # | The order identifier |
| Customer | Customer name |
| Project | Project name |
| Date | Order date |
| Total | Total order value (EUR) |
| Remaining | Outstanding balance (EUR) |

## Related Articles

- [Filters & Date Ranges](/docs/user-guide/filters) — Full walkthrough of date presets, custom ranges, and chart controls.
- [HR Dashboard](/docs/user-guide/hr-dashboard) — View HR metrics alongside your sales data.
- [Uploading Data](/docs/user-guide/uploading-data) — Add new sales data to the dashboard.
