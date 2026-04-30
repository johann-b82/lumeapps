# Mobile UI hygiene pass — design

**Date:** 2026-04-30
**Status:** approved (brainstorm)
**Driver:** several admin surfaces (dashboard SubHeader, Signage admin tabs, employee/sales tables, settings color grid, NavBar) overflow at narrow viewports. The originally-flagged offender was the date-range pill in `SubHeader`. Audit confirmed five other surfaces in the same situation.

## Scope

This pass — internally referenced as scope **B** — touches the dashboard surfaces and the obvious narrow-screen offenders:

- `frontend/src/components/dashboard/DateRangeFilter.tsx`
- `frontend/src/components/SubHeader.tsx` (Signage 4-tab pill only; the 2-segment Sales/HR toggle stays as-is)
- `frontend/src/components/dashboard/EmployeeTable.tsx` (inline 3-segment overtime/active/all pill, plus the table itself)
- `frontend/src/components/dashboard/SalesTable.tsx` (table itself)
- `frontend/src/pages/SettingsPage.tsx` (6-column color grid)
- `frontend/src/components/NavBar.tsx` (density cuts)

**Out of scope:** Upload page, Sensors page, Signage detail screens (Pair / Devices / Schedules), Player kiosk, Login. KPI card grids (already responsive `grid-cols-1 lg:grid-cols-3`). Tablet-only breakpoints. New mobile-only navigation patterns (drawer, bottom nav).

## Goal

Every page in scope is usable at 375 px viewport width:

- No horizontal page scroll above the fold.
- Every interactive control is reachable without the page reflowing into an unreadable layout.
- Tables are scrollable horizontally with a clear visual cue, but no data is hidden.

## Non-goals

- Mobile-first or mobile-native UX. This is an internal admin tool used primarily on desktop; mobile is a fallback, not a primary surface.
- Card-list table rewrites or row-detail modals.
- A `useMediaQuery` hook or container-query system.
- Adding a separate tablet breakpoint.

## Approach

**Strategy:** Tailwind breakpoint, `md:` (768 px). Single component dual-renders both layouts; one is hidden via `hidden md:block` / `md:hidden`. Both branches are mounted in the React tree — cost is one extra DOM subtree per swapped component, which is negligible (small `<select>` elements; not large pickers).

**Mobile primitive for pill swaps:** the existing shadcn `<Select>` at `frontend/src/components/ui/select.tsx`. Both branches consume the same source-of-truth array of options.

**Mobile primitive for tables:** `overflow-x-auto` wrapper around the existing `<table>`, plus a `min-width` on the table so columns don't compress to unreadable widths. No column hiding, no card list.

## Components

### 1. `DateRangeFilter`

Wrap the existing `<SegmentedControl>` in `<div className="hidden md:block">`. Add a parallel `<div className="md:hidden"><Select>...</Select></div>` rendering the same 4 presets (`thisMonth`, `thisQuarter`, `thisYear`, `allTime`). Single `PRESETS` array; both renderers consume it. Same `selectPreset(p)` handler called from both. `aria-label="Date range"` on both.

### 2. `SubHeader` Signage 4-tab pill

Identical dual-render swap. Each tab item maps to a `wouter` route; the same `navigate(target.path)` handler runs from both branches. The Sales/HR 2-segment `<Toggle>` and `SensorTimeWindowPicker` remain unchanged.

### 3. `EmployeeTable` inline 3-segment pill

The overtime/active/all `<SegmentedControl>` lives inside the table card header alongside the title and search input. Apply the same dual-render swap.

### 4. `SalesTable` and `EmployeeTable` table bodies

Wrap each `<table>` in `<div className="overflow-x-auto">`. Add `min-w-[640px]` (Sales, 6 columns) / `min-w-[760px]` (Employee, 8 columns) on the table element. Visual cue for scrollability comes from the visible right-edge truncation; no extra "swipe" affordance added (consistent with the rest of the SaaS-tool style).

### 5. `SettingsPage` color grid (`SettingsPage.tsx:201`)

Change `grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4` to `grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4`. Two-column layout at 375 px is fine; the `md:grid-cols-3` middle step was making 3-up cards crowded between 768–1023 px without solving the small-screen case.

### 6. `NavBar` density cuts

At `md:` and below:

- **Hide the `<Breadcrumb>`.** It's redundant with the SubHeader's visible tabs and the page content.
- **Move `<ThemeToggle>` and `<LanguageToggle>` into `<UserMenu>`** as new menu items, leaving the right-side bar with just the docs icon and the avatar/UserMenu trigger.

Above `md:`, both stay on the bar exactly as they are today.

`UserMenu` already renders other items (Docs, Settings, Sign-out per v1.19). The two new items reuse the existing `<DropdownItem>` primitive with the toggle's current value shown on the right-hand side of the row (e.g. "Theme · Light"); tapping the row cycles to the next value (light → dark → system → light for theme; en → de for language). No nested submenu, no inline pill — keeps the menu visually consistent with existing items.

## Data flow

No new state. Existing `useDateRange()`, `wouter` router, per-component `useState` (filter pill in `EmployeeTable`) all remain. The `Select` component's `onValueChange` calls the same handler the `SegmentedControl` already uses.

## Testing

For each swapped component (`DateRangeFilter`, `SubHeader` Signage tabs, `EmployeeTable` filter pill), one new vitest test asserting that:

1. Both desktop and mobile renderers are present in the rendered tree (assert by query selector — `[role="radiogroup"]` for the pill, `[role="combobox"]` for the Select).
2. Selecting an option on the mobile renderer invokes the same `onChange` handler with the same payload as selecting on the desktop renderer.

For tables, no new tests — the change is purely a wrapper class and a min-width.

For NavBar density cuts: since the swap is implemented purely with Tailwind `hidden md:block` / `md:hidden` (no JS branching on `matchMedia`), assertions test the **DOM contract**, not the CSS hide/show. One vitest test for `NavBar` asserting the breadcrumb element renders with class `hidden md:block` (or equivalent — Tailwind class assertion), and one for `UserMenu` asserting the new theme/lang items render with class `md:hidden`. Visual verification of actual hide/show behaviour at width happens via Chrome DevTools mobile emulation in the acceptance step.

No new Playwright e2e; the smoke-rebuild Playwright test is still gated behind `SMOKE_REBUILD_E2E=1` (v1.24 deferred), so adding mobile-viewport e2e here would compound that debt.

## Edge cases

- **Tablet (768–1023 px)** uses the desktop layout. We don't add a third breakpoint.
- **Pi player kiosk** is unaffected — separate `player.html` bundle.
- **i18n** — labels come from existing `t()` calls; no new keys.
- **A11y** — the dropdown swap uses the shadcn `<Select>`, which is keyboard- and screen-reader-accessible by default.

## Risks

- **NavBar density cuts** — moving theme/lang into UserMenu changes the discoverability of those toggles on mobile. Acceptable for an admin tool; flagged for the user to push back if mobile theme switching is a frequent action.
- **`min-w-[640px]` / `min-w-[760px]` on tables** — chosen by adding column widths from current CSS; if column content grows (e.g., longer customer names) the min-width may need to grow with it. Not a hard regression — table will just demand more horizontal scroll.

## Acceptance

- All six surfaces verified at 375 px in Chrome DevTools mobile emulation, no horizontal page scroll, every control reachable.
- Existing desktop layout unchanged at ≥ 768 px.
- New vitest tests pass.
- `pytest -q` and `npm run build` still green (no new warnings, no new errors).
