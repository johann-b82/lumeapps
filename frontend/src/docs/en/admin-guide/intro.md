# Admin Guide

The Admin Guide covers everything you need to set up, configure, and maintain the KPI Dashboard. Whether you are deploying the application for the first time or managing an existing installation, these articles walk you through each aspect of the system.

## System Setup

Learn how to configure environment variables, start the Docker Compose stack, and verify that all services are running. This is the place to start if you are deploying the KPI Dashboard for the first time.

[Read the System Setup guide](/docs/admin-guide/system-setup)

## Architecture

Understand how the services fit together -- from the PostgreSQL database through the FastAPI backend to the React frontend, plus Directus for identity management. Covers the startup sequence, data flow, and tech stack.

[Read the Architecture overview](/docs/admin-guide/architecture)

## Digital Signage

Provision Raspberry Pi kiosks, build playlists, and assign them to devices via tags. Covers media intake (drag-and-drop, URL/HTML, PPTX conversion), schedules, and offline behavior.

[Read the Digital Signage guide](/docs/admin-guide/digital-signage)

## Personio Integration

Configure the connection to Personio for automatic HR data synchronization, including credentials, sync intervals, and attribute mapping.

[Read the Personio Integration guide](/docs/admin-guide/personio)

## Sensor Monitor

Onboard SNMP environmental sensors (temperature + humidity), set polling cadence and thresholds, and configure per-sensor chart colors.

[Read the Sensor Monitor guide](/docs/admin-guide/sensor-monitor)

## User Management

Manage user roles and access through Directus, including administrator and viewer role setup.

[Read the User Management guide](/docs/admin-guide/user-management)

## Settings layout (since v1.28)

The Settings page is split into peer pages — **General**, **HR**, and **Sensors** — selectable via a dropdown in the sub-header. Each page has its own draft and Save/Discard bar; switching sections with unsaved changes prompts you before discarding.

## Related Articles

- [System Setup](/docs/admin-guide/system-setup)
- [Architecture](/docs/admin-guide/architecture)
- [Digital Signage](/docs/admin-guide/digital-signage)
- [Personio Integration](/docs/admin-guide/personio)
- [Sensor Monitor](/docs/admin-guide/sensor-monitor)
- [User Management](/docs/admin-guide/user-management)
