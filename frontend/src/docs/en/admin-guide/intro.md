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

## Embedded Apps (v1.46+ / v1.48+)

Three optional third-party apps ship with the stack but stay off by default. Each runs under its own Docker Compose profile so a small deployment can skip what it does not need:

- **Documents — Paperless-ngx** (`paperless` profile, v1.46+) — mounted at `/paperless/*`, Postgres-backed, full Directus SSO via `X-Remote-User`. Local users are auto-provisioned on first hit.
- **PDF Tools — Stirling-PDF** (`stirling` profile, v1.48+) — mounted at `/pdf/*`, community edition with internal login disabled. Caddy `forward_auth` is the only auth gate.
- **Projects — OpenProject** (`openproject` profile, v1.48+) — mounted at `/op/*`, dedicated `openproject` Postgres database. The Caddy gate keeps unauthenticated browsers off the OP login page; the community edition has no header SSO so users authenticate against OpenProject separately on first visit. Set `OPENPROJECT_ADMIN_PASSWORD` in `.env` before bringing the profile up.

Enable a profile with `docker compose --profile <name> up -d`. Multiple profiles compose; list them all in `COMPOSE_PROFILES` in `.env` to bring them up together.

## Settings layout

The Settings area is split into three pages — **General**, **HR**, and **Sensors** — picked from the section dropdown at the top of the page. Each page has its own Save and Discard buttons; switching to another section while you have unsaved changes asks for confirmation first.

## Related Articles

- [System Setup](/docs/admin-guide/system-setup)
- [Architecture](/docs/admin-guide/architecture)
- [Digital Signage](/docs/admin-guide/digital-signage)
- [Personio Integration](/docs/admin-guide/personio)
- [Sensor Monitor](/docs/admin-guide/sensor-monitor)
- [User Management](/docs/admin-guide/user-management)
