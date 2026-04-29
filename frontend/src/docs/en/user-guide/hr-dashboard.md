# HR Dashboard

The HR Dashboard displays workforce KPIs sourced from Personio. It shows five key metrics, trend charts, and a detailed employee table. This article explains how to read each section and what to do if the dashboard shows no data.

## Requirements: Personio Connection

HR data is pulled directly from Personio. The dashboard state depends on whether Personio is configured and synced:

- **Not configured** — Each KPI card shows "—" with the label "not configured" and a link to **Open Settings**. Navigate to Settings to enter your Personio Client ID and Client Secret.
- **Configured, never synced** — A banner appears: "No data synced yet — Click 'Refresh data' or configure auto-sync in Settings." Trigger a manual sync or set an auto-sync interval in Settings.
- **Sync error** — A red banner shows "Could not load HR KPIs". Check your connection and click **Refresh data** to retry.
- **Configured with data** — KPI cards show current values with delta badges.

## Syncing Data

The **Refresh data** button in the page header triggers a manual Personio sync. After clicking it:

1. The button shows a loading state while the sync runs.
2. On success, a toast notification confirms "Sync complete".
3. On failure, a toast shows "Sync failed". Check your Personio credentials in Settings.

The header also shows the last sync time: **Last sync: {date and time}**, or "Not yet synced" if no sync has run.

## KPI Cards

Five KPI cards are displayed in a 3 + 2 layout:

| KPI | Unit | Description |
|-----|------|-------------|
| Overtime Ratio | % | Overhours divided by total worked hours of active employees |
| Sick Leave Ratio | % | Proportion of working time lost to sick leave |
| Fluctuation | % | Employee turnover rate |
| Skill Development | % | Share of employees with skill-related attributes |
| Revenue / Prod. Employee | EUR | Revenue per production employee |

### Delta Badges

Each card shows two delta badges: vs. the prior month and vs. the prior year. The HR dashboard uses today's date as its reference point — there is no date filter on this page. If no comparison data is available, the badge shows a tooltip: "No comparison period available".

## Trend Charts

Below the KPI cards, the HR charts section shows trend lines for each KPI over time.

- Use the **Area** / **Bar** toggle to switch the chart view.
- Charts update automatically after each Personio sync.

## Employee Table

The **Employees** table lists all employees retrieved from Personio.

- **Search** — Type in the search box to filter by name, department, or position.
- **Filter** — Use the filter control to show **All**, **Active**, or **With overtime** employees.

Table columns:

| Column | Description |
|--------|-------------|
| Name | Employee full name |
| Department | Personio department |
| Position | Job title |
| Status | Active / Inactive |
| Hire date | Date the employee joined |
| Hours/week | Contracted weekly hours |
| Worked | Actual hours worked |
| Overtime | Overtime hours |
| OT % | Overtime as a percentage of worked hours |

> **Note:** The HR dashboard has no date range filter. All metrics are calculated relative to the current date using data from the most recent Personio sync. For Sales date filters, see [Filters & Date Ranges](/docs/user-guide/filters).

## Related Articles

- [Sales Dashboard](/docs/user-guide/sales-dashboard) — Revenue KPIs with date range filtering.
- [Filters & Date Ranges](/docs/user-guide/filters) — Date presets and chart controls (Sales dashboard).
- [Language & Dark Mode](/docs/user-guide/language-and-theme) — Customise the interface language and colour scheme.
