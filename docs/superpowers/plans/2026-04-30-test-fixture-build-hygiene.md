# v1.24 — Test Fixture + Frontend Build Hygiene Catch-up

**Created:** 2026-04-30
**Driver:** v1.23 D-5 verification surfaced that `pytest -q`, `./scripts/smoke-rebuild.sh`, and `cd frontend && npm run build` have been broken on `main` since the initial commit (`7a22f03`). They were masked by a collection error in `test_color_validator.py`. v1.23's D-5 was narrowed to the contract guards it actually introduced; full-suite green is this phase's job.

## Goal

`pytest -q`, `./scripts/smoke-rebuild.sh`, and `cd frontend && npm run build` all exit 0 on `main`, with no skipped tests beyond explicitly marked integration ones.

## Scope

### Phase A — Backend test auth fixtures

**Problem:** `backend/tests/conftest.py` provides a single `client` fixture that yields an unauthenticated `httpx.AsyncClient`. Routers use router-level `dependencies=[Depends(get_current_user)]` (see `backend/app/routers/settings.py:37`), so any test that calls them gets 401. Newer signage tests work around this by minting their own JWTs via `_mint` from `tests/test_directus_auth.py`. ~7 older test files (`test_settings_api.py`, `test_kpi_chart.py`, `test_kpi_endpoints.py`, `test_rebuild_seed.py`, `test_rebuild_assert.py`, `test_rebuild_cleanup.py`, `test_signage_broadcast_integration.py`) predate that pattern.

**Tasks:**
- A-1: Add `admin_client` and `viewer_client` fixtures to `backend/tests/conftest.py` that wrap `client` with a pre-minted Directus JWT in default headers (use the existing `_mint` from `test_directus_auth.py` — promote it to `tests/_auth.py` as a shared helper, update its current importers).
- A-2: Migrate `test_settings_api.py` from `client` → `admin_client` (writes) / `viewer_client` (reads).
- A-3: Migrate `test_kpi_chart.py` and `test_kpi_endpoints.py` to `viewer_client`.
- A-4: Migrate `test_rebuild_seed.py`, `test_rebuild_assert.py`, `test_rebuild_cleanup.py` to `admin_client` (they hit `/api/settings` writes).
- A-5: Fix `test_signage_broadcast_integration.py` — investigate whether asyncpg `signage_pg_listen: initial connect failed` is a missing fixture (POSTGRES_HOST=db inside container vs localhost outside) or a real bug.
- A-6: Verify: `docker compose exec api pytest -q` exits 0.

### Phase B — Frontend build cleanup

**Problem:** `cd frontend && npm run build` fails with TS errors:
- `src/components/dashboard/EmployeeTable.tsx:30-31` — `string | undefined` not assignable to `string`
- `src/signage/lib/signageApi.ts:205,610,698` — `void → null` casts flagged
- `src/tests/contracts/adapter.contract.test.ts` — missing `@types/node` (uses `node:fs`, `node:path`, `node:url`, `process`)
- `src/tests/contracts/error-contract.test.ts:101..234` — `Mock<Procedure | Constructable>` not callable (vitest type signature mismatch)

**Tasks:**
- B-1: Install `@types/node` as devDependency, add `"node"` to `tsconfig.json` `types`. Verify the contract tests under `src/tests/contracts/` compile.
- B-2: Fix `EmployeeTable.tsx:30-31` `string | undefined` — add a guard or default.
- B-3: Fix `signageApi.ts` `void → null` casts at L205, L610, L698 — likely the `void` is a return type mismatch; trace and correct properly (no `as unknown as null` shortcut).
- B-4: Fix `error-contract.test.ts` Mock type — likely a vitest version drift; either pin vitest types or update the call signature.
- B-5: Verify: `cd frontend && npm run build` exits 0 with zero `error TS`.

### Phase C — Smoke-rebuild + CI re-enable

- C-1: Verify `./scripts/smoke-rebuild.sh` exits 0 (depends on A-4 making `test_rebuild_seed.py` green).
- C-2: Add a CI workflow (or extend existing `.github/`) that runs `pytest -q` + `npm run build` on every PR, so this debt cannot re-accumulate.
- C-3: Final summary commit: `chore: v1.24 test fixture + build hygiene complete`.

## Out of scope

- Refactoring how routers depend on `get_current_user` (the convention from v1.23 stands).
- Adding new tests beyond what's needed to migrate existing ones to fixtures.
- Touching frontend logic — fixes are TypeScript-only.

## Risks

- A-5 (signage_pg_listen) may surface a real bug rather than a fixture gap. If so, scope-creep into a small Phase D.
- B-3's `void → null` casts may be hiding real return-type bugs in `signageApi.ts`. Don't paper over with `as unknown`.
