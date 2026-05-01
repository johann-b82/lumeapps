# Sensor Monitor

## Overview

The Sensor Monitor polls environmental SNMP sensors (temperature + humidity) from the shared Docker network, stores readings in PostgreSQL, and surfaces them on the admin-only `/sensors` dashboard. Onboarding is entirely UI-driven -- no YAML or SQL access required.

All sensor configuration lives under **Settings → Sensors** — pick **Sensors** from the section dropdown at the top of the Settings page. Sensors is a full page in its own right, not an overlay. Only administrators see it.

## Prerequisites

1. The `api` container must be able to reach the sensor host over SNMP/UDP 161. Verify with:

   ```bash
   docker compose exec api snmpget -v2c -c public 192.9.201.27 1.3.6.1.4.1.21796.4.9.3.1.5.2
   ```

   A numeric response means you are good to go. A timeout means the Docker bridge cannot route to the sensor subnet -- see [Troubleshooting → Host-mode fallback](#host-mode-fallback) below.
2. Admin role on the KPI Dashboard. Viewer accounts cannot open the Sensors settings page.
3. The sensor host must be powered on and responding to SNMPv2c on UDP 161. SNMPv3 auth/priv is not supported in this release.

> **Note:** The smoke test uses `snmpget` from inside the `api` container on purpose -- reachability from your laptop or the Docker host is not sufficient. The scheduler runs inside the container, so that is where routing must work.

## Onboarding a Sensor

Open **Settings → Sensors** — pick **Sensors** from the section dropdown at the top of the Settings page.

### Step 1: Discover OIDs with SNMP Walk

1. Expand **SNMP Walk (OID finder)**.
2. Enter the sensor host, port (default 161), community string, and a base OID (for Kirchhoff sensors, start with `.1.3.6.1.4.1.21796.4.9.3.1`).
3. Click **Run walk**. Results appear in a scrollable table with OID, type, value.
4. Identify the temperature and humidity OIDs (typically ending in `.5.1` and `.6.1` for Kirchhoff).

### Step 2: Add a sensor row

1. Click **+ Add sensor**.
2. Fill name, host, port, community, and scale factors (1.0 for raw values; 10.0 if the sensor returns integer deci-°C).
3. In the Walk results, click **Assign** on the temperature OID → pick the new row → **Temp OID**. Repeat for humidity.

| Field          | Required | Notes                                                                 |
|----------------|----------|-----------------------------------------------------------------------|
| Name           | Yes      | Unique across all sensors                                             |
| Host           | Yes      | IP or DNS name reachable from the `api` container                     |
| Port           | Yes      | Default 161                                                           |
| Community      | No       | Write-only secret, encrypted at rest. Optional — leave blank if the device accepts SNMPv2c without authentication. |
| Temperature OID| No       | Leave blank to skip temperature for this sensor                       |
| Temperature scale | Yes   | Positive number; 1.0 or 10.0 typical                                  |
| Humidity OID   | No       | Leave blank to skip humidity for this sensor                          |
| Humidity scale | Yes      | Positive number; 1.0 or 10.0 typical                                  |
| Chart color    | No       | Hex color (`#RRGGBB`) for this sensor's line on the Sensors dashboard. Blank = next color from the default palette. |
| Enabled        | Yes      | Disable to stop polling without deleting the row                      |

### Step 3: Probe

1. Click **Probe** on the sensor row. Live temperature + humidity appear inline on success.
2. If the probe fails: double-check host reachability, community, and OID validity.

### Step 4: Save

Click **Save**. The sensor persists; the scheduler picks it up on the next tick. Switch to `/sensors` to confirm the new card appears with live readings.

## Thresholds

Global thresholds apply to all sensors. Set them in the **Global thresholds** card:

- Temperature min / max (°C)
- Humidity min / max (%)

When a reading falls outside the range, the KPI card shows a destructive (red-tinted) value and an "Out of range" caption. Charts draw dashed reference lines at each threshold.

> **Known limitation:** Leaving a threshold input blank means "do not change". To clear a previously-set threshold, contact the operator to unset it directly in the database or wait for a future release that adds an explicit reset action.

Per-sensor threshold overrides are not supported in this release.

## Polling Interval

The **Polling cadence** card sets a single interval (5–86400 seconds) for all enabled sensors. Saving triggers a live reschedule -- no API restart required.

Recommendations:

- 60 s (default): typical production environmental monitoring
- 30 s: for tight threshold alerting (planned future feature)
- 300+ s: for low-frequency baseline monitoring

| Interval | Daily polls per sensor | Typical use case                |
|----------|------------------------|---------------------------------|
| 30 s     | 2 880                  | Tight monitoring / alerting prep|
| 60 s     | 1 440                  | Default production              |
| 300 s    | 288                    | Baseline monitoring             |
| 3 600 s  | 24                     | Hourly summaries only           |

## Troubleshooting

### Sensor appears "Offline"

The health chip on `/sensors` reads **Offline for Xm** when three consecutive polls fail. Likely causes:

1. **Docker-to-sensor reachability broken** -- run the Prerequisites smoke test.
2. **Community string mismatch** -- sensor rotated credentials. Edit the row, enter the new community (leave blank to keep the current one), save.
3. **OID drift** -- the sensor firmware changed OID mapping. Re-run SNMP Walk to rediscover.

### <a id="host-mode-fallback"></a>Host-mode fallback

If `docker compose exec api snmpget ...` times out but the same command on the host machine succeeds, the Docker bridge cannot route to the sensor subnet. Two fallback options:

**Option A -- `network_mode: host` on the `api` service (simpler, more invasive):**

```yaml
services:
  api:
    network_mode: host
    # NOTE: incompatible with `ports:` + breaks internal Docker DNS (api → db).
    # All internal service references must switch to `localhost:<port>`.
    # Also requires removing the `networks:` stanza for this service.
```

Trade-offs:

- Breaks service discovery by name -- change `DATABASE_URL` from `db:5432` to `localhost:5432` and adjust every internal reference.
- Exposes the API on the host interface directly (bypasses Docker's network isolation).
- `ports:` declarations on `api` become invalid and must be removed.

**Option B -- `macvlan` network (less invasive, more config):**

```yaml
networks:
  sensor_lan:
    driver: macvlan
    driver_opts:
      parent: eth0
    ipam:
      config:
        - subnet: 192.9.201.0/24
          gateway: 192.9.201.1
          ip_range: 192.9.201.240/28

services:
  api:
    networks:
      default:
      sensor_lan:
        ipv4_address: 192.9.201.241
```

Attach the `api` service to a macvlan network that shares the host's L2 domain with the sensor subnet. This preserves Docker DNS and service isolation but requires a dedicated subnet range and IP reservation outside the DHCP pool. Recommended only when Option A's trade-offs are unacceptable.

**Preferred order:** stay on the default bridge → Option B (macvlan) → Option A (host mode) as a last resort.

### Polling runs but no readings appear

Check the logs:

```bash
docker compose logs api --tail=100 | grep -i sensor
```

Look for `PollResult` entries. Empty result sets with no errors usually mean the OID returned `noSuchObject` -- re-run SNMP Walk.

### Scheduler did not pick up the new cadence

The polling-interval input triggers an in-process reschedule on save. If the previous interval persists:

1. Reload the Sensors settings page and confirm the value was saved.
2. If the value is correct but behavior is not, restart the `api` container: `docker compose restart api`.

## Security

> **Community is optional.** Some SNMP devices (e.g., certain Hutermann models) accept queries without a community string — leave the field blank in that case. If your device requires a community, **never use the default `public` in production**: change it on the device to a per-deployment secret before exposing the monitor.

> **Community strings are encrypted at rest** using the application's Fernet key (same key as Personio credentials). They are never decrypted into API responses and never logged. The admin form treats community as write-only: blank on edit preserves the stored value, a new string overwrites it.

Additional guidance:

- Rotate community strings on the sensor device when an admin leaves the team; update the row on the Sensors settings page afterwards (blank = keep).
- Restrict SNMP on the sensor host to the Docker host's source IP where the device firmware allows it.
- Keep the sensor subnet off the public internet.

## Related Articles

- [System Setup](/docs/admin-guide/system-setup) -- Docker Compose overview
- [Architecture](/docs/admin-guide/architecture) -- how the scheduler integrates
- [Personio Integration](/docs/admin-guide/personio) -- sibling admin integration
