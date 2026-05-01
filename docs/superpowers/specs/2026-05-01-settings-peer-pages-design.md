# Settings restructure — peer pages with SubHeader dropdown nav

**Date:** 2026-05-01
**Status:** approved (brainstorm)
**Driver:** the current `/settings` route is one long scrolling page with three Card sections (Identity & Colors, HR, Sensors-link). User wants each section on its own page, navigation via dropdown, and Sensors as a peer page (not feeling like a child overlay of Settings).

## Goal

Three peer routes under `/settings/*`. Each renders one section with its own draft + ActionBar + unsaved-changes guard. A `<Select>` in the SubHeader is the only navigation between sections.

## Non-goals

- Promoting Sensors out of `/settings/*` (path stays nested; behavior changes from "link card" to "peer in dropdown").
- Splitting `SettingsUpdate` into per-section payloads on the backend.
- Lazy-loading sections.
- Folding the Sensors page into the unified `useSettingsDraft`. Sensors keeps its own draft.

## Routes

```
/settings              → wouter <Redirect to="/settings/general" />
/settings/general      → app_name + logo + 6 colors                (NEW page)
/settings/hr           → Personio + HR targets                     (NEW page)
/settings/sensors      → existing SensorsSettingsPage               (unchanged file)
```

`/settings/sensors` MUST remain registered before `/settings/*` in the wouter route table, mirroring today's first-match-wins ordering.

## Components

### `SettingsSectionPicker` (new)

Lives in `frontend/src/components/SettingsSectionPicker.tsx`. Renders the same v1.25 `<Select>` pattern as `DateRangeFilter`:

- Reads current section from `useLocation()`.
- Three options: `general` / `hr` / `sensors` with translated labels.
- `<SelectValue>` uses an explicit `(value) => label` render prop (v1.25 base-ui workaround).
- `data-testid="settings-section-picker-trigger"`.
- `aria-label={t("settings.section_picker.aria")}`.

`onValueChange(section)` calls into a shared `useSettingsSection().go(section)` hook (described below). The picker itself does NOT know whether the current page is dirty; it delegates.

### `useSettingsSection` (new hook)

Lives in `frontend/src/hooks/useSettingsSection.ts`. Returns:

```ts
{
  section: 'general' | 'hr' | 'sensors';
  go: (next: 'general' | 'hr' | 'sensors') => void;
}
```

`section` is parsed from the path — `/settings/<section>` (defaulting to `'general'` for the bare `/settings` redirect target). `go(next)` calls `navigate(`/settings/${next}`)` directly. The unsaved-guard interception happens inside `useUnsavedGuard` (existing hook, already wired into the global location-change listener) — `go` does NOT need to inspect dirty state itself.

### `SubHeader` change

In `frontend/src/components/SubHeader.tsx`, add a branch:

```tsx
{location.startsWith("/settings") && <SettingsSectionPicker />}
```

Place it in the same left-hand cluster as the existing `DateRangeFilter` / signage tabs / sensor time-window picker — all are mutually exclusive on their respective routes.

### `GeneralSettingsPage` (new)

Lives in `frontend/src/pages/GeneralSettingsPage.tsx`.

- Owns a draft via `useSettingsDraft({ slice: 'general' })`.
- Renders identity fields (`app_name`, `LogoUpload`) and the 6-`ColorPicker` grid that today lives in the `Identity & Colors` Card on `SettingsPage`.
- Includes the existing sticky `ActionBar` and `ResetDialog` and `UnsavedChangesDialog`.
- `Save` posts a `SettingsUpdate` with only general-slice fields; backend already accepts partial updates.
- Page H1: `t("settings.general.title")` (translated "Allgemein"/"General").

### `HrSettingsPage` (new)

Lives in `frontend/src/pages/HrSettingsPage.tsx`.

- Owns a draft via `useSettingsDraft({ slice: 'hr' })`.
- Renders existing `<PersonioCard … embedded />` and `<HrTargetsCard … embedded />` components.
- Same sticky `ActionBar` + dialogs.
- `Save` posts a `SettingsUpdate` with only HR-slice fields.
- Page H1: `t("settings.hr.title")`.

### `SettingsRedirect` (new — tiny)

Lives in `frontend/src/pages/SettingsPage.tsx` (REPURPOSED, file kept). Renders `<Redirect to="/settings/general" />` and nothing else. The old long-scrolling implementation is split between the two new pages and deleted from this file.

### `useSettingsDraft` adjustment

Add a `slice` parameter:

```ts
type SettingsSlice = 'general' | 'hr';
const { draft, setField, isDirty, getDiffPayload, discard, save } =
  useSettingsDraft({ slice: 'general' });
```

`isDirty` and `getDiffPayload` only consider the named slice's fields. Slice membership is defined as a constant in the hook file:

```ts
const GENERAL_FIELDS = [
  'app_name', 'color_primary', 'color_accent', 'color_background',
  'color_foreground', 'color_muted', 'color_destructive',
] as const;

const HR_FIELDS = [
  'personio_client_id', 'personio_client_secret', 'personio_sync_interval_h',
  'personio_sick_leave_type_id', 'personio_production_dept',
  'personio_skill_attr_key',
  'target_overtime_ratio', 'target_sick_leave_ratio',
  'target_fluctuation', 'target_revenue_per_employee',
] as const;
```

`logo` upload is its own endpoint (`POST /api/settings/logo`) and stays out of the slice diff — it's already a separate mutation today.

## Data flow

```
User clicks SettingsSectionPicker → onValueChange("hr")
  → useSettingsSection.go("hr")
    → wouter.navigate("/settings/hr")
      → useUnsavedGuard global listener intercepts (if isDirty)
        → opens UnsavedChangesDialog
          → "Stay"          : cancel navigation, no-op
          → "Discard+leave" : discard draft, complete navigation
      → otherwise: navigate fires normally
        → React Router unmounts /settings/general, mounts /settings/hr
        → /settings/hr's useSettingsDraft({slice:'hr'}) initializes
          from the latest GET /api/settings response
```

The unsaved-guard wiring is unchanged from today — `useUnsavedGuard` already hooks into wouter location changes. We just add the picker as a new entry point that triggers a navigation.

## Edge cases

- **Bare `/settings`** — `SettingsRedirect` renders `<Redirect to="/settings/general" />`. Existing bookmarks to `/settings` still resolve.
- **Mobile (≤ 768 px)** — `SettingsSectionPicker` is a `<Select>`, already mobile-correct. No breakpoint logic.
- **`/settings/sensors`** — picker shows "Sensoren" as the active value. Selecting "Allgemein"/"HR" navigates to the corresponding new page; the existing Sensors `useUnsavedGuard` keeps its own behavior.
- **Locale parity** — four new i18n keys (en + de):
  - `settings.section.general` → "General" / "Allgemein"
  - `settings.section.hr` → "HR" / "HR"
  - `settings.section.sensors` → "Sensors" / "Sensoren"
  - `settings.section_picker.aria` → "Settings section" / "Einstellungs­abschnitt"
- **Document title** — each page sets `document.title` to `${app_name} · ${section_label}` via the existing pattern (no new helper).
- **Direct deep link to a section the user has no role for** — admin-only fields surface server-side errors as today; no client-side gating change. (`AdminOnly` wrappers around fields that already have them stay.)

## Testing

- `vitest` tests for `SettingsSectionPicker`:
  1. Renders the trigger with `data-testid="settings-section-picker-trigger"`.
  2. Selecting an option calls wouter `navigate` with the right path (memory-location spy, mirrors A-2 from v1.25).
  3. Active value reflects the current path (renders "HR" label when path is `/settings/hr`).
- `vitest` test for `useSettingsSection`: section is correctly parsed from `/settings`, `/settings/general`, `/settings/hr`, `/settings/sensors`.
- `vitest` test for the `<Redirect>` at `/settings`: rendering at `/settings` resolves to `/settings/general`.
- `vitest` tests for `GeneralSettingsPage` and `HrSettingsPage`:
  - Each renders the testids the SubHeader picker uses to switch in (one per page: `settings-page-general` / `settings-page-hr`).
  - Each renders the sticky ActionBar (assert by testid).
- No new tests for `useSettingsDraft({slice})` — the slice field set is a plain constant array; correctness is provided by the page-level tests above (they assert that saving "general" doesn't include HR fields in the payload, by intercepting `fetch`).

## Files

```
NEW
  frontend/src/components/SettingsSectionPicker.tsx
  frontend/src/hooks/useSettingsSection.ts
  frontend/src/pages/GeneralSettingsPage.tsx
  frontend/src/pages/HrSettingsPage.tsx
  frontend/src/components/__tests__/SettingsSectionPicker.test.tsx
  frontend/src/hooks/__tests__/useSettingsSection.test.ts
  frontend/src/pages/__tests__/GeneralSettingsPage.test.tsx
  frontend/src/pages/__tests__/HrSettingsPage.test.tsx

MODIFY
  frontend/src/App.tsx               — register routes /settings/general + /settings/hr; /settings → redirect
  frontend/src/pages/SettingsPage.tsx — replace body with <Redirect to="/settings/general" />
  frontend/src/components/SubHeader.tsx — add SettingsSectionPicker branch on /settings/*
  frontend/src/hooks/useSettingsDraft.ts — accept `slice` param; isDirty/getDiffPayload restricted to slice
  frontend/src/locales/en.json       — 4 new keys
  frontend/src/locales/de.json       — 4 new keys

DELETE (extracted into the two new pages)
  (no file deletions — SettingsPage.tsx stays as the redirect)
```

## Risks

- **`useSettingsDraft` slice param touches the existing hook.** Today there is exactly one call site (`pages/SettingsPage.tsx`); two `DraftFields` type imports in `PersonioCard.tsx` and `HrTargetsCard.tsx` aren't affected. The migration replaces the single call site with the two new page components, each passing its own slice. The `slice` parameter is therefore required — no default, no `'all'` fallback. This keeps the API tight and forces every future caller to declare which slice it owns.
- **Mobile dropdown overlap with the Sales/HR toggle on `/sales`/`/hr`.** Not a concern: the section picker only renders when `location.startsWith("/settings")`. Mutually exclusive with the dashboard left-cluster controls.
- **Two simultaneous PUT requests if a user switches sections fast while a save is in flight.** Mitigation: each page's ActionBar already disables Save while a save is pending (`isSaving` state). The unsaved-guard prevents leaving with a dirty draft.

## Acceptance

- `/settings` resolves to `/settings/general` (200 + body matches the new general page).
- The SubHeader on `/settings/*` shows a `<Select>` with three options. Selecting any option navigates to the corresponding peer page.
- A dirty draft on one page produces the existing `UnsavedChangesDialog` when the user switches via the picker.
- Save on `/settings/general` produces a `PUT /api/settings` payload containing only general-slice fields (asserted via vitest fetch spy).
- Save on `/settings/hr` produces a payload containing only HR-slice fields.
- Sensors page works exactly as today (no functional change).
- `cd frontend && npm run build` exits 0.
- `cd frontend && npx vitest run` is green (existing 255 + new tests).
- `docker compose exec api pytest -q` baseline (366) preserved — no backend changes.
