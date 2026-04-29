# Filters & Date Ranges

The KPI Dashboard lets you control what time window and chart style you see on each dashboard. This article explains the date range filter, the chart type control, and how delta badges respond to your selection.

## Date Range Filter

The date range filter appears at the top of the **Sales Dashboard**. It is a segmented control with four presets:

| Preset | What it shows |
|---|---|
| **This month** | Data from the first day of the current calendar month to today |
| **This quarter** | Data from the start of the current quarter (Q1 = Jan, Q2 = Apr, Q3 = Jul, Q4 = Oct) |
| **This year** | Data from 1 January of the current year to today |
| **All time** | All data in the database, regardless of date |

The default selection is **This month**. Your selection persists while you stay on the Sales Dashboard and resets when you navigate away.

> **Note:** The date range filter applies to the Sales Dashboard only. The HR Dashboard always shows data relative to the current date and does not have a date range filter.

## Chart Type Control

### Sales Dashboard — Revenue Chart

In the top-right corner of the Revenue over time chart, a segmented control lets you switch between:

- **Bar** — A bar chart (default). Columns are grouped by the granularity of the selected period.
- **Area** — A filled area chart. Useful for spotting overall trends at a glance.

### HR Dashboard — HR Charts

On the HR Dashboard, each chart has its own chart type control in its top-right corner:

- **Area** — A filled area chart (default).
- **Bar** — A bar chart.

## Delta Badge Behaviour

Delta badges appear on KPI cards and indicate how the current period compares to a reference period. The badges shown depend on the active date range preset:

| Active preset | Badges shown |
|---|---|
| **This month** | vs. prior month · vs. same month prior year |
| **This quarter** | vs. prior quarter · vs. same quarter prior year |
| **This year** | vs. prior year YTD (one badge only) |
| **All time** | No badges |

For a full explanation of how delta values are calculated, see the [Sales Dashboard](sales-dashboard) article.

## Related Articles

- [Sales Dashboard](sales-dashboard)
- [HR Dashboard](hr-dashboard)
