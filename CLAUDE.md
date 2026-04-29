## Project

**LumeApps**

A Dockerized web application for uploading sales/revenue data files (CSV, TXT, Excel) into a PostgreSQL database and visualizing KPIs on an interactive dashboard. Built for internal team use, secured behind a self-hosted Directus 11 identity provider (email/password, Admin + Viewer roles, HS256-shared-secret JWT).

**Core Value:** Upload a data file and immediately see sales/revenue KPIs visualized on a dashboard — zero friction from raw data to insight.

### Constraints

- **Containerization**: Must run via Docker Compose — no bare-metal dependencies
- **Database**: PostgreSQL — chosen for reliability and ecosystem
- **Identity**: Directus 11 — self-hosted, single-container, runs alongside Postgres; email/password + two built-in roles (Admin, Viewer); FastAPI validates Directus-issued HS256 JWTs on every `/api/*` request. (Shipped v1.11-directus 2026-04-15.)
- **File schema**: Fixed/known columns — simplifies parsing, no schema inference needed

## Principles

Behavioral guidelines for working in this repo. Bias toward caution over speed; for trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

**Working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, clarifying questions before implementation rather than after mistakes.

---

## Technology Stack

## Recommended Stack
### Backend Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | 0.135.3 | REST API, file upload endpoint, data endpoints | Fastest Python web framework for async I/O; native async support matches our PostgreSQL async driver; automatic OpenAPI docs save time; UploadFile built-in for multipart forms. Flask/Django are sync-first and add unnecessary complexity for this use case. |
| Uvicorn | 0.44.0 | ASGI server | Standard ASGI server for FastAPI; production-ready with `--workers` flag. Do NOT use `--reload` in Docker production container. |
| python-multipart | 0.0.26 | Multipart form parsing (required by FastAPI for file uploads) | FastAPI's UploadFile depends on this at runtime — it is a hard requirement, not optional. |
| Pydantic v2 | >=2.9.0 (via FastAPI) | Request/response validation, config management | Bundled with FastAPI 0.135.x; v2 is ~10x faster than v1; use BaseSettings for environment config. |
### Database Layer
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | 17-alpine (Docker image) | Primary database | Project constraint. Use `postgres:17-alpine` tag — v17 is current LTS, alpine image is ~50% smaller than debian variant. Do NOT use `latest` tag; it changes without warning and can break on major version upgrades. |
| SQLAlchemy | 2.0.49 | ORM and query builder | Industry standard; v2.0 async API is stable and production-proven. Use `AsyncSession` with `create_async_engine`. Do NOT use the legacy 1.x-style patterns (pre-2.0 `Session` with sync engine) — mixing sync and async causes subtle deadlocks in FastAPI. |
| asyncpg | 0.31.0 | Async PostgreSQL driver | Required by SQLAlchemy 2.0 async engine (`postgresql+asyncpg://`). Significantly faster than psycopg2 in async contexts. psycopg3 is an alternative but asyncpg has more FastAPI ecosystem examples and is battle-tested. |
| Alembic | 1.18.4 | Database schema migrations | Standard migration tool for SQLAlchemy; auto-generates migration scripts from model diffs. IMPORTANT: Alembic uses a *sync* engine even in async apps — configure a separate sync `sqlalchemy.url` in `alembic.ini`. Never call `Base.metadata.create_all()` directly; always go through Alembic so migration history stays consistent. |
### File Parsing
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pandas | 3.0.2 | Parse CSV, TXT (delimited), and Excel files into DataFrames | Single library handles all three input formats with a consistent API (`pd.read_csv`, `pd.read_excel`). For a fixed-schema ingestion pipeline, pandas is significantly simpler than managing separate parsers. Works via `io.BytesIO` on FastAPI's `UploadFile.read()` bytes — no temp file on disk needed. |
| openpyxl | 3.1.5 | Excel (.xlsx/.xls) engine used by pandas | pandas' `read_excel()` requires openpyxl as the backend for .xlsx files. It is a runtime dependency, not a dev dependency. Install alongside pandas; do not skip it or pandas will fail at runtime with an ImportError. |
### Frontend Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| React | 19.2.5 | UI framework | Standard for interactive dashboards; large ecosystem; hooks-based state management fits dashboard update patterns. |
| TypeScript | 5.x (via Vite template) | Type safety | Prevents a class of runtime errors in data-binding code (API response → chart data); minimal overhead in this project size. |
| Vite | 8.0.8 | Build tool and dev server | Internal tool with no SEO requirements — Next.js SSR adds complexity with zero benefit here. Vite's HMR is near-instant; produces smaller bundles than Next.js (~42KB vs ~92KB baseline). Use the `vite create` React-TS template. |
### UI and Charting
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Tailwind CSS | 4.2.2 | Utility-first styling | Fastest path to a polished internal UI without a design system. v4 drops the `tailwind.config.js` file in favor of CSS-first config — note this is a breaking change from v3 docs. |
| shadcn/ui | latest (copy-paste, no npm package version) | Component primitives (cards, tables, buttons) | Unstyled Radix UI components + Tailwind classes; copy-paste pattern means no "component library update" breaking changes. Use for summary KPI cards, upload form, upload history table. |
| Recharts | 3.8.1 | Line charts and bar charts for KPI trends | SVG-based (not canvas), React-native API, directly composable with TypeScript. Tremor is built on Recharts but adds abstraction overhead; for a project of this size, raw Recharts gives more control with similar effort. Chart.js/react-chartjs-2 is canvas-based — harder to style and customize individual elements. |
| @tanstack/react-query | 5.97.0 | Server state management and data fetching | Handles loading/error states, caching, and refetching for API calls. Avoids writing boilerplate `useEffect` + `useState` data fetching. Use for dashboard data endpoints and upload history. Do NOT use Redux or Zustand for server state — that's the wrong tool. |
### Infrastructure
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Docker | latest engine (runtime) | Containerize app | Project constraint. |
| Docker Compose | v2 (compose v2.x plugin) | Orchestrate app + PostgreSQL containers | Project constraint. Use `docker compose` (v2, no hyphen) syntax — `docker-compose` (v1, Python CLI) is end-of-life. |
## Docker Compose Pattern
- Use `condition: service_healthy` on `depends_on` — not just `depends_on: db`. Without this the app container starts before PostgreSQL accepts connections, causing startup crashes.
- `pg_isready` is built into the official postgres image — no extra tools needed.
- Store all credentials in a `.env` file; never hardcode in `docker-compose.yml`.
- Run Alembic migrations as a Docker Compose startup command or a separate migration service that exits after completion, before the API service starts.
## Alternatives Considered
| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Backend framework | FastAPI | Django REST Framework | Django's ORM is sync-first; adds migration/admin overhead not needed for this scope |
| Backend framework | FastAPI | Flask | No async support; no automatic validation; more boilerplate for same result |
| Async PG driver | asyncpg | psycopg3 (async) | asyncpg has deeper FastAPI ecosystem support and more examples; psycopg3 async is newer and less documented in this context |
| File parsing | pandas | Pure csv module + openpyxl | Would require separate code paths per format; pandas handles all three uniformly |
| Frontend build | Vite + React | Next.js | No SSR or SEO requirement; Next.js complexity is wasted; Vite is faster and simpler |
| Charting | Recharts | Tremor | Tremor is a higher-level abstraction built on Recharts; adds a dependency with less control |
| Charting | Recharts | Chart.js / react-chartjs-2 | Canvas-based; harder to customize; not React-native; SVG (Recharts) is easier to style with Tailwind |
| CSS | Tailwind v4 | CSS Modules | Tailwind is faster for internal UI iteration; CSS Modules add file-switching overhead |
| State management | TanStack Query | Redux Toolkit | Redux is for complex client-side state; server-fetched data is TanStack Query's domain |
| DB migrations | Alembic | SQLAlchemy `create_all()` | `create_all()` provides no migration history or rollback capability |
## Installation
### Backend (Python — add to `requirements.txt` or `pyproject.toml`)
### Frontend (npm)
# Install shadcn/ui via its CLI (copy-paste pattern)
## Confidence Assessment
| Area | Confidence | Source |
|------|------------|--------|
| FastAPI 0.135.3 version | HIGH | Verified against PyPI API directly |
| pandas 3.0.2 version | HIGH | Verified against PyPI API directly |
| SQLAlchemy 2.0.49 version | HIGH | Verified against PyPI API directly |
| asyncpg 0.31.0 version | HIGH | Verified against PyPI API directly |
| alembic 1.18.4 version | HIGH | Verified against PyPI API directly |
| openpyxl 3.1.5 version | HIGH | Verified against PyPI API directly |
| uvicorn 0.44.0 version | HIGH | Verified against PyPI API directly |
| python-multipart 0.0.26 | HIGH | Verified against PyPI API directly |
| React 19.2.5 version | HIGH | Verified against npm registry directly |
| Recharts 3.8.1 version | HIGH | Verified against npm registry directly |
| Vite 8.0.8 version | HIGH | Verified against npm registry directly |
| Tailwind CSS 4.2.2 version | HIGH | Verified against npm registry directly |
| TanStack Query 5.97.0 | HIGH | Verified against npm registry directly |
| postgres:17-alpine Docker image | HIGH | Verified against Docker Hub tag listing |
| FastAPI + asyncpg async pattern | HIGH | Official FastAPI docs + SQLAlchemy 2.0 async docs |
| Docker Compose healthcheck pattern | HIGH | Official Docker documentation + community verification |
| Recharts over Tremor/Chart.js | MEDIUM | Multiple comparison articles; no single authoritative benchmark |
| Vite over Next.js for internal tools | HIGH | Multiple independent sources consistently agree on this split |
## Sources
- [FastAPI Full Stack Template (official)](https://fastapi.tiangolo.com/project-generation/)
- [FastAPI Request Files — official docs](https://fastapi.tiangolo.com/tutorial/request-files/)
- [SQLAlchemy 2.0 Async I/O docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [FastAPI + SQLAlchemy 2.0 async patterns (Dec 2025)](https://dev-faizan.medium.com/fastapi-sqlalchemy-2-0-modern-async-database-patterns-7879d39b6843)
- [Alembic + FastAPI best practices (2025)](https://blog.greeden.me/en/2025/08/12/no-fail-guide-getting-started-with-database-migrations-fastapi-x-sqlalchemy-x-alembic/)
- [Docker Compose healthcheck for PostgreSQL](https://eastondev.com/blog/en/posts/dev/20251217-docker-compose-healthcheck/)
- [How to Use the Postgres Docker Official Image](https://www.docker.com/blog/how-to-use-the-postgres-docker-official-image/)
- [Best React Chart Libraries 2025 — LogRocket](https://blog.logrocket.com/best-react-chart-libraries-2025/)
- [Vite vs Next.js 2025 comparison — Strapi](https://strapi.io/blog/vite-vs-nextjs-2025-developer-framework-comparison)
- [Fastest way to load data into PostgreSQL with Python](https://hakibenita.com/fast-load-data-python-postgresql)

## Conventions

### Auth gate placement

Auth dependencies live at the router (or `APIRouter` sub-package) level. Per-route `Depends(require_admin)` is permitted only when a router mixes viewer-readable and admin-only endpoints, and the module docstring must declare which endpoints are admin-only. See `backend/tests/test_admin_gate_audit.py` for the CI guard.

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.

