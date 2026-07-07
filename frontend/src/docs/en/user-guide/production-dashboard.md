# Production dashboard

The Production perspective shows how reliably your orders are delivered on time. The first section, **Orders overdue**, combines four KPI tiles at the top, an overdue-rate history chart below, and two tables: the orders delivered late and the overdue orders that are still open. Everything can be filtered by date range.

![Production perspective: KPIs and history with target line](/docs/produktion-uebersicht.png)

Open the perspective from the **Production** tile on the launcher, or via the perspective switcher at the top left.

## What counts as "overdue"?

An order belongs to the period of its **target date** (the latest planned delivery date across its positions). Within the selected range, an order is counted once its outcome is decided, and it is **overdue** if either condition holds:

- **Delivered late** — the order has a delivery note, and its last delivery came after the target date.
- **Open & overdue** — the order has no delivery note yet, and the target date is already in the past.

Orders whose target date is still in the future and that have not been delivered are **pending** — they are excluded from both the overdue count and the denominator, because their outcome is not yet decided.

## KPI tiles

- **Overdue rate** — share of orders due in the period that were delivered late or are overdue & open. Lower is better.
- **Orders overdue** — number of overdue orders (delivered late **plus** open & overdue).
- **Orders total** — number of orders due in the period (the rate's denominator).
- **Avg delay** — average lateness in days.

The overdue-rate tile shows delta badges vs. the previous period and previous year once a comparison range exists. Because a **low** rate is good, an improvement renders green.

## Overdue rate over time

The bar chart shows the overdue rate per time bucket. Use the **−** / **+** buttons at the top right to change the granularity (weekly / monthly / quarterly / yearly); the from/to fields let you pick a custom range.

### Configurable target line

If a target value is configured in settings, a dashed **target line** appears in the chart (e.g. `Target 2.0 %`). Bars above the line exceed the target.

Set the value under **Settings → Production → Max. overdue rate** (as a percentage). Clearing the field hides the line.

![Configuring the target line under Settings → Production](/docs/produktion-ziellinie.png)

## The two tables

Below the chart, two tables sit side by side. Together they make up the overdue orders, split by category. Both are searchable and sortable via the column headers.

![Tables: orders overdue and overdue open orders](/docs/produktion-tabellen.png)

- **Orders overdue** — the orders delivered late, sorted by delay descending. Columns: order, customer, target date, actual delivery, delay (days).
- **Overdue open orders** — the not-yet-delivered orders whose target date has already passed — the acute action list. Columns: order, customer, target date, days overdue.

## Feeding the data

The perspective is fed by two exports you upload on the Upload page:

- **Order positions (AUF, position-level)** — provides the target date per order position.
- **Deliveries (delivery notes)** — provides the actual delivery dates.

See [Uploading data](/docs/user-guide/uploading-data) for how to upload, and [Filters & date ranges](/docs/user-guide/filters) for the range presets and custom ranges.
