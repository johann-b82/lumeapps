# Sales Dashboard

The Sales Dashboard gives you a real-time view of your revenue performance. It combines three KPI summary cards, a "Revenue over time" chart, and a searchable orders table — all filterable by date range. This article explains each element and how to read the data.

## KPI Cards

At the top of the dashboard, three cards summarise your key metrics for the selected period:

- **Total revenue** — The sum of all order values, displayed in EUR.
- **Average order value** — Total revenue divided by the number of orders, in EUR.
- **Total orders** — The count of all orders in the selected period.

> **Note:** Orders with a value of €0 are excluded from all three KPI calculations.

### Delta Badges

Each card shows one or two delta badges that compare the current period to a reference period:

- **This month** — Shows two badges: vs. the prior month and vs. the same month in the prior year.
- **This quarter** — Shows two badges: vs. the prior quarter and vs. the prior year.
- **This year** — Shows a single badge: vs. the prior year (year-to-date comparison).
- **All time** — No delta badges are shown.
- **Custom range** — No delta badges are shown.

If no comparison data is available, the badge shows a tooltip: "No comparison period available".

## Revenue over Time Chart

Below the KPI cards, the **Revenue over time** chart visualises revenue across the selected period.

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

## Orders Table

Below the chart, the **Orders** table lists every order in the selected date range. You can:

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

## Sales Activity

Below the revenue chart, the **Sales activity** card shows four weekly line charts — one per KPI, with one line per sales rep:

| KPI | What it counts |
|-----|----------------|
| First contacts | New leads (Typ = ERS in the Kontakte file) |
| Prospects | Inquiries that look like an early sales conversation (Typ ∈ {ANFR, EPA}) |
| Visits | On-site customer visits (Typ = ORT) |
| Quotes | Quotes recorded against a contact (any row whose comment starts with "Angebot") |

Sales reps are taken straight from the `Wer` column in the uploaded Kontakte file (e.g. `KARRER`, `GUENDEL`). No Personio mapping is involved.

All four charts respect the dashboard's date-range filter and use the same color per rep so a person reads as the same line across the four charts.

## Order Distribution

Below the activity charts, the **Order distribution** card shows three numbers for the selected date range:

| Metric | What it shows |
|--------|---------------|
| Orders / week / rep | Mean number of orders per sales rep per week. Orders are attributed to a rep when a Kontakte row mentions that order's number ("Angebot 5000000"). |
| Top-3 customer share | Percentage of total order value coming from the top-3 customers. The subtitle lists those customers. |
| Remaining customers | 100 % minus the top-3 share — the long-tail share of revenue. |

Both the activity charts and the distribution card stay empty until at least one Kontakte file has been uploaded.

## Related Articles

- [Filters & Date Ranges](/docs/user-guide/filters) — Full walkthrough of date presets, custom ranges, and chart controls.
- [HR Dashboard](/docs/user-guide/hr-dashboard) — View HR metrics alongside your sales data.
- [Uploading Data](/docs/user-guide/uploading-data) — Add new sales data to the dashboard.
