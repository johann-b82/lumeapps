# Mobile UI Hygiene Pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dashboard, signage admin, settings, and NavBar surfaces usable at 375 px viewport, per spec [`docs/superpowers/specs/2026-04-30-mobile-ui-hygiene-design.md`](../specs/2026-04-30-mobile-ui-hygiene-design.md).

**Architecture:** Tailwind `md:` (768 px) breakpoint. Each affected component dual-renders both layouts; one is hidden via `hidden md:block` / `md:hidden`. Pill swaps use the existing shadcn `<Select>` for mobile. Tables get an `overflow-x-auto` wrapper. NavBar density cuts move `ThemeToggle` + `LanguageToggle` into `UserMenu` below `md:`.

**Tech Stack:** React 19 + TypeScript + Tailwind v4 + shadcn/ui + base-ui Select + wouter, vitest + @testing-library/react for tests.

**Spec adjustment baked into plan:** The spec referenced cycling theme as "light → dark → system → light" — but the existing `ThemeToggle` is a 2-segment Toggle (`light` ↔ `dark`); a "system" mode exists implicitly only when `localStorage.theme` is unset. The mobile menu items expose the same 2-mode toggle the desktop bar already exposes. No new theme states.

---

# Phase A — Pill → dropdown swaps

Three components, each gets one commit.

## Task A-1: `DateRangeFilter` dual-render

**Files:**
- Modify: `frontend/src/components/dashboard/DateRangeFilter.tsx`
- Create: `frontend/src/components/dashboard/__tests__/DateRangeFilter.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/dashboard/__tests__/DateRangeFilter.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n";
import { DateRangeFilter } from "@/components/dashboard/DateRangeFilter";
import { getPresetRange } from "@/lib/dateUtils";

function renderFilter(onChange: (...args: unknown[]) => void) {
  const range = getPresetRange("thisMonth");
  return render(
    <I18nextProvider i18n={i18n}>
      <DateRangeFilter
        value={{ from: range.from, to: range.to }}
        preset="thisMonth"
        onChange={onChange}
      />
    </I18nextProvider>,
  );
}

describe("DateRangeFilter", () => {
  it("mounts both desktop and mobile renderers", () => {
    renderFilter(vi.fn());
    expect(screen.getByTestId("date-range-filter-desktop")).toBeInTheDocument();
    expect(screen.getByTestId("date-range-filter-mobile")).toBeInTheDocument();
  });

  it("desktop renderer is hidden below md (className contract)", () => {
    renderFilter(vi.fn());
    expect(screen.getByTestId("date-range-filter-desktop")).toHaveClass(
      "hidden",
      "md:block",
    );
  });

  it("mobile renderer is hidden at md+ (className contract)", () => {
    renderFilter(vi.fn());
    expect(screen.getByTestId("date-range-filter-mobile")).toHaveClass(
      "md:hidden",
    );
  });

  it("desktop pill exposes a radiogroup with 4 segments", () => {
    renderFilter(vi.fn());
    const desktop = screen.getByTestId("date-range-filter-desktop");
    const radiogroup = desktop.querySelector('[role="radiogroup"]');
    expect(radiogroup).not.toBeNull();
    expect(radiogroup!.querySelectorAll('[role="radio"]')).toHaveLength(4);
  });

  it("mobile renderer exposes a Select trigger", () => {
    renderFilter(vi.fn());
    const mobile = screen.getByTestId("date-range-filter-mobile");
    expect(mobile.querySelector('[data-slot="select-trigger"]')).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `cd frontend && npx vitest run src/components/dashboard/__tests__/DateRangeFilter.test.tsx`
Expected: FAIL — `data-testid="date-range-filter-desktop"` not found (today's component has no testid wrapper).

- [ ] **Step 3: Rewrite `DateRangeFilter.tsx` to dual-render**

```tsx
// frontend/src/components/dashboard/DateRangeFilter.tsx
import { useTranslation } from "react-i18next";
import { SegmentedControl } from "@/components/ui/segmented-control";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getPresetRange, type Preset } from "@/lib/dateUtils";

export interface DateRangeValue {
  from: Date | undefined;
  to: Date | undefined;
}

interface DateRangeFilterProps {
  value: DateRangeValue;
  preset: Preset;
  onChange: (value: DateRangeValue, preset: Preset) => void;
}

const PRESETS: Preset[] = ["thisMonth", "thisQuarter", "thisYear", "allTime"];

export function DateRangeFilter({
  value: _value,
  preset,
  onChange,
}: DateRangeFilterProps) {
  const { t } = useTranslation();

  const selectPreset = (p: Preset) => {
    const range = getPresetRange(p);
    onChange({ from: range.from, to: range.to }, p);
  };

  const segments = PRESETS.map((p) => ({
    value: p,
    label: t(`dashboard.filter.${p}`),
  }));

  return (
    <>
      <div data-testid="date-range-filter-desktop" className="hidden md:block">
        <SegmentedControl<Preset>
          segments={segments}
          value={preset}
          onChange={selectPreset}
          aria-label="Date range"
        />
      </div>
      <div data-testid="date-range-filter-mobile" className="md:hidden">
        <Select<Preset>
          value={preset}
          onValueChange={selectPreset}
        >
          <SelectTrigger className="w-44" aria-label="Date range">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {segments.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </>
  );
}
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `cd frontend && npx vitest run src/components/dashboard/__tests__/DateRangeFilter.test.tsx`
Expected: PASS — 5 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dashboard/DateRangeFilter.tsx \
        frontend/src/components/dashboard/__tests__/DateRangeFilter.test.tsx
git commit -m "feat(A-1): DateRangeFilter dual-renders pill + Select for mobile"
```

---

## Task A-2: `SubHeader` Signage 4-tab pill dual-render

**Files:**
- Modify: `frontend/src/components/SubHeader.tsx` (Signage tabs block, ~line 146-156 today)
- Create: `frontend/src/components/__tests__/SubHeaderSignageTabs.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/__tests__/SubHeaderSignageTabs.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Router, useLocation } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { I18nextProvider } from "react-i18next";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18n from "@/i18n";
import { SubHeader } from "@/components/SubHeader";
import { DateRangeProvider } from "@/contexts/DateRangeContext";

function renderAt(path: string, navigate: ReturnType<typeof vi.fn>) {
  const memory = memoryLocation({ path });
  // Wrap memoryLocation's navigate with our spy so we can assert on calls.
  const wrappedHook = () => {
    const [loc] = useLocation();
    return [loc, navigate] as const;
  };
  void memory; // memory.hook unused — we replace with wrappedHook above
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>
        <DateRangeProvider>
          <Router hook={wrappedHook as never}>
            <SubHeader />
          </Router>
        </DateRangeProvider>
      </I18nextProvider>
    </QueryClientProvider>,
  );
}

describe("SubHeader signage tabs", () => {
  beforeEach(() => {
    // Avoid noisy logs from useQuery hooks that don't need to actually fetch.
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    );
  });

  it("mounts both desktop and mobile renderers when on a signage admin tab route", () => {
    renderAt("/signage/playlists", vi.fn());
    expect(
      screen.getByTestId("signage-tabs-desktop"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("signage-tabs-mobile")).toBeInTheDocument();
  });

  it("does not render signage tabs on /signage/pair", () => {
    renderAt("/signage/pair", vi.fn());
    expect(screen.queryByTestId("signage-tabs-desktop")).toBeNull();
    expect(screen.queryByTestId("signage-tabs-mobile")).toBeNull();
  });

  it("mobile Select navigates via wouter on change", async () => {
    const navigate = vi.fn();
    renderAt("/signage/playlists", navigate);
    const trigger = screen
      .getByTestId("signage-tabs-mobile")
      .querySelector('[data-slot="select-trigger"]') as HTMLElement;
    await userEvent.click(trigger);
    // base-ui Select renders items in a portal; query global screen.
    await userEvent.click(screen.getByRole("option", { name: /devices/i }));
    expect(navigate).toHaveBeenCalledWith("/signage/devices");
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `cd frontend && npx vitest run src/components/__tests__/SubHeaderSignageTabs.test.tsx`
Expected: FAIL — `data-testid="signage-tabs-desktop"` not found.

- [ ] **Step 3: Rewrite the Signage-tabs block in `SubHeader.tsx`**

Locate the existing block:

```tsx
{showSignageTabs && (
  <SegmentedControl
    segments={signageTabs.map((tab) => ({ value: tab.id, label: t(tab.labelKey) }))}
    value={signageActive}
    onChange={(id) => {
      const target = signageTabs.find((tab) => tab.id === id);
      if (target) navigate(target.path);
    }}
    aria-label={t("signage.admin.page_title")}
  />
)}
```

Replace with:

```tsx
{showSignageTabs && (
  <>
    <div data-testid="signage-tabs-desktop" className="hidden md:block">
      <SegmentedControl
        segments={signageTabs.map((tab) => ({ value: tab.id, label: t(tab.labelKey) }))}
        value={signageActive}
        onChange={(id) => {
          const target = signageTabs.find((tab) => tab.id === id);
          if (target) navigate(target.path);
        }}
        aria-label={t("signage.admin.page_title")}
      />
    </div>
    <div data-testid="signage-tabs-mobile" className="md:hidden">
      <Select
        value={signageActive}
        onValueChange={(id) => {
          const target = signageTabs.find((tab) => tab.id === id);
          if (target) navigate(target.path);
        }}
      >
        <SelectTrigger className="w-40" aria-label={t("signage.admin.page_title")}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {signageTabs.map((tab) => (
            <SelectItem key={tab.id} value={tab.id}>
              {t(tab.labelKey)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  </>
)}
```

Add the missing imports near the existing `SegmentedControl` import:

```tsx
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `cd frontend && npx vitest run src/components/__tests__/SubHeaderSignageTabs.test.tsx`
Expected: PASS — 3 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SubHeader.tsx \
        frontend/src/components/__tests__/SubHeaderSignageTabs.test.tsx
git commit -m "feat(A-2): SubHeader signage tabs dual-render pill + Select"
```

---

## Task A-3: `EmployeeTable` filter-pill dual-render

**Files:**
- Modify: `frontend/src/components/dashboard/EmployeeTable.tsx` (the inline 3-segment SegmentedControl in the card header)
- Create: `frontend/src/components/dashboard/__tests__/EmployeeTableFilter.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/dashboard/__tests__/EmployeeTableFilter.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18n from "@/i18n";
import { EmployeeTable } from "@/components/dashboard/EmployeeTable";
import { DateRangeProvider } from "@/contexts/DateRangeContext";

function renderTable() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>
        <DateRangeProvider>
          <EmployeeTable />
        </DateRangeProvider>
      </I18nextProvider>
    </QueryClientProvider>,
  );
}

describe("EmployeeTable filter pill", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("[]", { status: 200 }),
    );
  });

  it("mounts both desktop and mobile renderers", () => {
    renderTable();
    expect(screen.getByTestId("employee-filter-desktop")).toBeInTheDocument();
    expect(screen.getByTestId("employee-filter-mobile")).toBeInTheDocument();
  });

  it("desktop renderer is hidden below md", () => {
    renderTable();
    expect(screen.getByTestId("employee-filter-desktop")).toHaveClass(
      "hidden",
      "md:block",
    );
  });

  it("mobile renderer is hidden at md+", () => {
    renderTable();
    expect(screen.getByTestId("employee-filter-mobile")).toHaveClass(
      "md:hidden",
    );
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `cd frontend && npx vitest run src/components/dashboard/__tests__/EmployeeTableFilter.test.tsx`
Expected: FAIL — testids not found.

- [ ] **Step 3: Modify `EmployeeTable.tsx`**

Find the existing block (current code, around the card header — verbatim from source as of plan-write time):

```tsx
<SegmentedControl<"overtime" | "active" | "all">
  segments={[
    { value: "overtime", label: t("hr.table.showOvertime") },
    { value: "active", label: t("hr.table.showActive") },
    { value: "all", label: t("hr.table.showAll") },
  ]}
  value={filter}
  onChange={setFilter}
/>
```

(Note: the existing source has no `aria-label` on this `<SegmentedControl>`. We do not add one — keep parity with the source.)

Replace with:

```tsx
{(() => {
  const segments = [
    { value: "overtime" as const, label: t("hr.table.showOvertime") },
    { value: "active" as const, label: t("hr.table.showActive") },
    { value: "all" as const, label: t("hr.table.showAll") },
  ];
  return (
    <>
      <div data-testid="employee-filter-desktop" className="hidden md:block">
        <SegmentedControl<"overtime" | "active" | "all">
          segments={segments}
          value={filter}
          onChange={setFilter}
        />
      </div>
      <div data-testid="employee-filter-mobile" className="md:hidden">
        <Select<"overtime" | "active" | "all">
          value={filter}
          onValueChange={setFilter}
        >
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {segments.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </>
  );
})()}
```

Add the missing imports at the top of `EmployeeTable.tsx`:

```tsx
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `cd frontend && npx vitest run src/components/dashboard/__tests__/EmployeeTableFilter.test.tsx`
Expected: PASS — 3 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dashboard/EmployeeTable.tsx \
        frontend/src/components/dashboard/__tests__/EmployeeTableFilter.test.tsx
git commit -m "feat(A-3): EmployeeTable filter pill dual-renders for mobile"
```

---

# Phase B — Tables, grid, NavBar density

## Task B-1: `SalesTable` table `min-width`

**Files:**
- Modify: `frontend/src/components/dashboard/SalesTable.tsx`

No new tests — the change is one className addition (per spec § "For tables, no new tests"). The existing source already wraps the `<table>` in `<div className="overflow-x-auto rounded-md border border-border">`, so this task only adds the `min-w` so columns don't compress at narrow viewports.

- [ ] **Step 1: Verify the existing wrapper is in place**

Run: `grep -n "overflow-x-auto" frontend/src/components/dashboard/SalesTable.tsx`
Expected: one match showing `<div className="overflow-x-auto rounded-md border border-border">`. If not, the spec assumption is broken — stop and surface to the user.

- [ ] **Step 2: Add `min-w-[640px]` to the `<table>` className**

Change:

```tsx
<table className="w-full text-sm">
```

To:

```tsx
<table className="w-full min-w-[640px] text-sm">
```

- [ ] **Step 3: Verify the build still compiles**

Run: `cd frontend && npm run build`
Expected: exit 0, zero `error TS`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dashboard/SalesTable.tsx
git commit -m "feat(B-1): SalesTable — table min-w-[640px] for mobile scroll"
```

---

## Task B-2: `EmployeeTable` table `min-width`

**Files:**
- Modify: `frontend/src/components/dashboard/EmployeeTable.tsx`

Existing source already has `<div className="overflow-x-auto rounded-md border border-border">`. Add `min-w-[760px]` to the `<table>` className.

- [ ] **Step 1: Add `min-w-[760px]` to the `<table>` className**

Change:

```tsx
<table className="w-full text-sm">
```

To:

```tsx
<table className="w-full min-w-[760px] text-sm">
```

- [ ] **Step 2: Verify the build still compiles**

Run: `cd frontend && npm run build`
Expected: exit 0, zero `error TS`.

- [ ] **Step 3: Re-run the EmployeeTable filter test from A-3**

Run: `cd frontend && npx vitest run src/components/dashboard/__tests__/EmployeeTableFilter.test.tsx`
Expected: PASS (3 tests, no regression from B-2).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dashboard/EmployeeTable.tsx
git commit -m "feat(B-2): EmployeeTable — table min-w-[760px] for mobile scroll"
```

---

## Task B-3: `SettingsPage` color grid breakpoint cleanup

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx` (line ~201 — the 6-column color grid)

- [ ] **Step 1: Find the grid line**

Run: `grep -n "grid-cols-2 md:grid-cols-3 lg:grid-cols-6" frontend/src/pages/SettingsPage.tsx`
Expected: one match, around line 201.

- [ ] **Step 2: Change the breakpoint sequence**

Replace `grid-cols-2 md:grid-cols-3 lg:grid-cols-6` with `grid-cols-2 sm:grid-cols-3 lg:grid-cols-6` on that single line. (Spec § Component 5: drop the `md:grid-cols-3` middle step that crowded 768–1023 px without solving small-screen.)

- [ ] **Step 3: Verify the build still compiles**

Run: `cd frontend && npm run build`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat(B-3): SettingsPage color grid — drop md:grid-cols-3 middle step"
```

---

## Task B-4: `NavBar` — hide breadcrumb below `md:`

**Files:**
- Modify: `frontend/src/components/NavBar.tsx`
- Modify: `frontend/src/components/Breadcrumb.test.tsx` (only if existing tests would catch our wrapper — see Step 2)

- [ ] **Step 1: Read NavBar and locate `<Breadcrumb />`**

Run: `grep -n "Breadcrumb" frontend/src/components/NavBar.tsx`

The existing line looks like:

```tsx
{!isLauncher && <Breadcrumb />}
```

- [ ] **Step 2: Wrap the Breadcrumb in a `hidden md:block` div**

Change to:

```tsx
{!isLauncher && (
  <div data-testid="navbar-breadcrumb-wrapper" className="hidden md:block">
    <Breadcrumb />
  </div>
)}
```

- [ ] **Step 3: Add a vitest case asserting the wrapper class contract**

Append to `frontend/src/components/__tests__/NavBar.test.tsx` if it exists, or create the file:

```tsx
// frontend/src/components/__tests__/NavBar.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { I18nextProvider } from "react-i18next";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18n from "@/i18n";
import { NavBar } from "@/components/NavBar";

vi.mock("@/auth/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "tester@example.com", role: "admin" },
    signOut: vi.fn(),
  }),
}));

function renderAt(path: string) {
  const { hook } = memoryLocation({ path });
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>
        <Router hook={hook}>
          <NavBar />
        </Router>
      </I18nextProvider>
    </QueryClientProvider>,
  );
}

describe("NavBar", () => {
  it("breadcrumb wrapper has hidden md:block (mobile-hide contract)", () => {
    renderAt("/sales");
    const wrapper = screen.getByTestId("navbar-breadcrumb-wrapper");
    expect(wrapper).toHaveClass("hidden", "md:block");
  });
});
```

- [ ] **Step 4: Run the new test, confirm it passes**

Run: `cd frontend && npx vitest run src/components/__tests__/NavBar.test.tsx`
Expected: PASS — 1 test.

- [ ] **Step 5: Run the existing Breadcrumb test suite, confirm no regression**

Run: `cd frontend && npx vitest run src/components/Breadcrumb.test.tsx`
Expected: same number of passes as before this task (the wrapper is invisible to that suite — `Breadcrumb` is rendered standalone there).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/NavBar.tsx \
        frontend/src/components/__tests__/NavBar.test.tsx
git commit -m "feat(B-4): NavBar — hide breadcrumb below md:"
```

---

## Task B-5: `UserMenu` — add Theme + Language items, mobile-only

**Files:**
- Modify: `frontend/src/components/UserMenu.tsx`
- Modify: `frontend/src/components/UserMenu.test.tsx`

- [ ] **Step 1: Read existing UserMenu and the toggle internals**

Run: `cat frontend/src/components/ThemeToggle.tsx frontend/src/components/LanguageToggle.tsx`

Confirm the current state semantics:
- Theme: 2-mode (`"light" | "dark"`), persisted to `localStorage.theme`, applied by toggling `.dark` on `<html>`.
- Language: 2-mode (`"de" | "en"`), persisted by `i18next` via `i18n.changeLanguage`.

The new menu items must reuse these same primitives — do **not** reinvent the persistence logic.

- [ ] **Step 2: Write a failing test asserting the new items render with `md:hidden`**

Append to `frontend/src/components/UserMenu.test.tsx`:

```tsx
import { describe as describeMobile, it as itMobile, expect as expectMobile } from "vitest";
import { fireEvent } from "@testing-library/react";
// (Reuse this file's existing render helper if present; else wrap as in NavBar.test.tsx.)

describeMobile("UserMenu mobile-only theme + language items", () => {
  itMobile("renders theme + language menu items wrapped with md:hidden", async () => {
    // Open the menu first (the avatar trigger is the only thing in the closed state).
    const { getByLabelText, findByTestId } = renderMenu(); // existing helper
    fireEvent.click(getByLabelText(/triggerLabel|avatar|user/i));

    const theme = await findByTestId("usermenu-theme-item");
    const lang = await findByTestId("usermenu-language-item");
    expectMobile(theme).toHaveClass("md:hidden");
    expectMobile(lang).toHaveClass("md:hidden");
  });
});
```

If `renderMenu` doesn't exist in the file, model after `Breadcrumb.test.tsx` — wrap in `Router` + `I18nextProvider` + `QueryClientProvider` and a `vi.mock("@/auth/useAuth", ...)` returning a stub user.

- [ ] **Step 3: Run the test, confirm it fails**

Run: `cd frontend && npx vitest run src/components/UserMenu.test.tsx`
Expected: FAIL — testids not found.

- [ ] **Step 4: Add the items in `UserMenu.tsx`**

Inside the `<DropdownContent>`, just above the existing final `<DropdownSeparator />` + Sign-out item, add:

```tsx
<DropdownSeparator className="md:hidden" />
<DropdownItem
  data-testid="usermenu-theme-item"
  className="md:hidden"
  onClick={(e) => {
    // Keep menu open isn't a hard requirement here — base-ui will close,
    // which is fine; the value persists via localStorage + .dark class.
    const root = document.documentElement;
    const next = root.classList.contains("dark") ? "light" : "dark";
    if (next === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
    localStorage.setItem("theme", next);
    void e;
  }}
>
  {t("userMenu.theme") /* if absent, fall back to literal "Theme" */}
</DropdownItem>
<DropdownItem
  data-testid="usermenu-language-item"
  className="md:hidden"
  onClick={() => {
    const next = i18n.language === "de" ? "en" : "de";
    void i18n.changeLanguage(next);
  }}
>
  {t("userMenu.language") /* if absent, fall back to literal "Language" */}
</DropdownItem>
```

Add imports at the top of `UserMenu.tsx`:

```tsx
import i18n from "@/i18n";
```

If a translation key (`userMenu.theme`, `userMenu.language`) doesn't exist in `frontend/src/i18n/locales/en.json` and `de.json`, add both. The English values are `"Theme"` and `"Language"`; the German values are `"Erscheinungsbild"` and `"Sprache"`.

- [ ] **Step 5: Run the test, confirm it passes**

Run: `cd frontend && npx vitest run src/components/UserMenu.test.tsx`
Expected: PASS — including the new test plus the existing UserMenu suite (no regression).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/UserMenu.tsx \
        frontend/src/components/UserMenu.test.tsx \
        frontend/src/i18n/locales/en.json \
        frontend/src/i18n/locales/de.json
git commit -m "feat(B-5): UserMenu — mobile-only Theme + Language items"
```

---

## Task B-6: `NavBar` — hide ThemeToggle + LanguageToggle below `md:`

**Files:**
- Modify: `frontend/src/components/NavBar.tsx`

- [ ] **Step 1: Locate the toggles in NavBar**

Run: `grep -n "ThemeToggle\|LanguageToggle" frontend/src/components/NavBar.tsx`

The existing block looks like:

```tsx
<ThemeToggle />
<LanguageToggle />
```

- [ ] **Step 2: Wrap each in a `hidden md:flex` div**

Change to:

```tsx
<div className="hidden md:flex">
  <ThemeToggle />
</div>
<div className="hidden md:flex">
  <LanguageToggle />
</div>
```

`md:flex` (not `md:block`) preserves the existing flex children semantics from the parent `flex items-center gap-4` row.

- [ ] **Step 3: Append test cases asserting the wrapper class contract**

Add to `frontend/src/components/__tests__/NavBar.test.tsx` (the file created in B-4):

```tsx
it("ThemeToggle wrapper has hidden md:flex", () => {
  renderAt("/sales");
  // ThemeToggle renders a Toggle radiogroup with aria-label "theme.toggle.aria_label"
  // (translated). Walk up to the wrapper.
  const themeRadiogroup = screen.getByLabelText(i18n.t("theme.toggle.aria_label"));
  const wrapper = themeRadiogroup.closest("div.hidden.md\\:flex");
  expect(wrapper).not.toBeNull();
});

it("LanguageToggle wrapper has hidden md:flex", () => {
  renderAt("/sales");
  const langRadiogroup = screen.getByLabelText(/language|sprache/i);
  const wrapper = langRadiogroup.closest("div.hidden.md\\:flex");
  expect(wrapper).not.toBeNull();
});
```

Add the import at the top if not already present:

```tsx
import i18n from "@/i18n";
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `cd frontend && npx vitest run src/components/__tests__/NavBar.test.tsx`
Expected: PASS — 3 tests now (1 from B-4, 2 from B-6).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/NavBar.tsx \
        frontend/src/components/__tests__/NavBar.test.tsx
git commit -m "feat(B-6): NavBar — hide ThemeToggle + LanguageToggle below md:"
```

---

# Phase C — Verification + ship

## Task C-1: Full vitest pass

- [ ] **Step 1: Run the entire frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: all green. No new failures vs. the pre-A baseline.

- [ ] **Step 2: If anything fails, fix it. Otherwise proceed.**

Likely culprits if a regression slipped in:
- Snapshot tests on NavBar / SubHeader / EmployeeTable that didn't account for the new wrappers — update the snapshot deliberately and inspect the diff.
- `closest` queries in B-6 — `closest` requires escaped colons in selectors when colons appear in CSS class names from Tailwind (e.g. `md\\:flex`).

---

## Task C-2: Acceptance — `pytest -q` + `npm run build` green

- [ ] **Step 1: Backend smoke**

Run: `docker compose exec -T api pytest -q`
Expected: 366 passed, 6 skipped, 59 deselected (matches v1.24 baseline). No new failures.

- [ ] **Step 2: Frontend build**

Run: `cd frontend && npm run build`
Expected: exit 0, zero `error TS`.

- [ ] **Step 3: Manual mobile-emulation acceptance check**

Open `http://localhost/sales` (or any dashboard route) in Chrome with DevTools mobile emulation set to **iPhone 13** (390×844). Verify:

- No horizontal page scroll above the fold on `/sales`, `/hr`, `/signage/playlists`, `/signage/devices`, `/signage/schedules`, `/signage/media`, `/settings`.
- Date-range selector renders as a `<Select>` dropdown (not a pill).
- Signage admin tabs render as a `<Select>` dropdown.
- HR table filter renders as a `<Select>` dropdown.
- Sales and HR tables scroll horizontally inside their card; rest of page does not scroll horizontally.
- NavBar shows logo + name + docs icon + avatar (no breadcrumb, no theme/lang toggles).
- Avatar menu, when opened, contains a Theme and Language item near the bottom.
- At ≥ 768 px (resize browser), all of the above flip back to the existing pill / inline-toggle layout.

If any item fails, file a follow-up commit before C-3.

---

## Task C-3: Ship commit

- [ ] **Step 1: Update README version-history table**

Append above the v1.24 row (`README.md:347` area):

```markdown
| v1.25 | 2026-04-30 | Mobile UI Hygiene Pass — six dashboard/admin surfaces (DateRangeFilter, SubHeader Signage tabs, EmployeeTable filter pill, SalesTable + EmployeeTable bodies, SettingsPage color grid, NavBar) made usable at 375 px. Pill→`<Select>` swap below `md:` (768 px); tables wrapped in `overflow-x-auto` with `min-w` so no data is hidden; SettingsPage drops the crowded `md:grid-cols-3` middle step; NavBar hides breadcrumb on mobile and moves Theme + Language toggles into UserMenu. Tailwind dual-render strategy — same component renders both layouts, one is hidden via `hidden md:block` / `md:hidden`. Six new vitest tests cover the DOM contract per swap. No backend changes. |
```

- [ ] **Step 2: Commit the README update**

```bash
git add README.md
git commit -m "docs(v1.25): add mobile UI hygiene to version history"
```

- [ ] **Step 3: Empty tag commit**

```bash
git commit --allow-empty -m "$(cat <<'EOF'
chore: v1.25 mobile UI hygiene pass complete

Verification (all green):
  - npx vitest run → all suites pass, +6 new tests
  - cd frontend && npm run build → exit 0, zero TS errors
  - docker compose exec api pytest -q → 366 passed, 6 skipped, 59 deselected
  - manual 390×844 mobile emulation: 7 routes pass acceptance

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Push to origin**

Confirm with the user before pushing — pushes are visible to others. After confirmation:

```bash
git push origin main
```

---

# Self-review notes

- Spec coverage: every component in spec § Components has a Phase-A or Phase-B task (DateRangeFilter → A-1; Signage tabs → A-2; EmployeeTable filter → A-3; tables → B-1, B-2; SettingsPage grid → B-3; NavBar density → B-4 + B-5 + B-6).
- Spec § Testing: A-1, A-2, A-3, B-4, B-5, B-6 each ship the vitest case the spec requires; B-1, B-2, B-3 are pure className changes per spec § "For tables, no new tests."
- Spec § Acceptance: Task C-2 step 3 enumerates the seven mobile-emulation routes.
- Spec adjustment: theme is 2-mode (light/dark), not 3-mode — flagged in plan header.
- Spec adjustment: both Sales and Employee tables already have an `overflow-x-auto` wrapper in source. B-1/B-2 narrowed to "add `min-w` only" — the wrapper is unnecessary work the spec didn't anticipate.
- Type consistency: `Preset`, `Language`, and the EmployeeTable filter literal-union (`"overtime" | "active" | "all"`) all stay consistent with the existing source.
- A-3 reads existing source (no `aria-label` on the inline pill) and preserves the source's lack of one — no fictional i18n keys.
