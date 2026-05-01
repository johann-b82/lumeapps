# Personio Integration

## Overview

Personio is the HR data source for absence rates, headcount, and skill tracking KPIs. The KPI Dashboard connects to your Personio instance via their API, synchronizes employee and absence data, and uses it to calculate HR KPIs such as Sick Leave Ratio, Revenue / Prod. Employee, and Skill Development.

## Entering Credentials

1. Open **Settings → HR** — pick **HR** from the section dropdown at the top of the Settings page. HR is its own page; you no longer scroll past General to reach it.
2. In the **Personio** section:
3. Enter your **Client ID** in the first field.
4. Enter your **Client Secret** in the second field.
5. Click **Test connection** to verify the credentials against the Personio API before saving.
6. If the test succeeds, click **Save changes** to persist the credentials.

Both fields are write-only password inputs -- you will not see previously saved values, only a hint that credentials are stored.

> **Note:** Treat API credentials as secrets. They are stored in the application database -- ensure your PostgreSQL instance is secured.

## Configuring Sync Interval

In the **Sync interval** dropdown next to the credential fields, choose how often data is fetched from Personio:

| Option        | Behavior                                      |
|---------------|-----------------------------------------------|
| Manual only   | Data is only fetched when you click "Refresh data" |
| Hourly        | Automatic sync every hour                     |
| Every 6 hours | Automatic sync four times a day               |
| Daily         | Automatic sync once every 24 hours            |
| Weekly        | Automatic sync once a week                    |

Select the interval that matches your reporting needs, then click **Save changes**.

## Mapping Fields

After credentials are saved and verified, three mapping sections become available. Options in each list are fetched live from your Personio instance.

### Sick Leave Type

Select one or more absence types from the list. These are used to calculate the **Sick Leave Ratio** KPI on the HR Dashboard. Only absence types defined in your Personio instance appear here.

### Production Department

Select one or more departments that count as production departments. These are used to calculate the **Revenue / Prod. Employee** KPI, which divides total revenue by the number of active employees in the selected departments.

### Skill Attribute Keys

Select one or more custom attributes from Personio that represent employee skills. These are used for the **Skill Development** KPI, which tracks how skill coverage evolves over time.

## Manual Sync

On the [HR Dashboard](/docs/user-guide/hr-dashboard), click the **Refresh data** button to trigger an immediate sync outside the scheduled interval. This fetches the latest data from Personio regardless of the configured sync schedule.

## Related Articles

- [HR Dashboard](/docs/user-guide/hr-dashboard) -- view the KPIs powered by Personio data
- [Architecture](/docs/admin-guide/architecture) -- understand how the sync service fits into the system
