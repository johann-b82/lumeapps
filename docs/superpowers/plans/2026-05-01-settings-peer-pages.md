# Settings Peer Pages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `/settings` into three peer routes (`/settings/general`, `/settings/hr`, `/settings/sensors`) with section selection via a `<Select>` in the SubHeader, per spec [`docs/superpowers/specs/2026-05-01-settings-peer-pages-design.md`](../specs/2026-05-01-settings-peer-pages-design.md).

**Architecture:** Three peer wouter routes with `/settings` redirecting to `/settings/general`. A new `SettingsSectionPicker` in the SubHeader publishes a navigation intent through `SettingsDraftContext` (extended with `pendingSection` + `requestSectionChange`). Each new page (`GeneralSettingsPage`, `HrSettingsPage`) owns its own draft slice via `useSettingsDraft({ slice })`, watches `pendingSection`, and reuses the existing `UnsavedChangesDialog`. Sensors page is untouched.

**Tech Stack:** React 19 + TypeScript + wouter 3.x + Tailwind v4 + base-ui Select wrapper, vitest + @testing-library/react.

**Spec correction baked into this plan:** The spec stated `useUnsavedGuard already hooks into wouter location changes` for the picker's programmatic navigation. That isn't true — the existing guard only intercepts anchor clicks, popstate, and beforeunload, not `navigate(...)` calls. The plan threads programmatic navigation through `SettingsDraftContext` (intent → page-rendered dialog) so the existing dialog UI stays unchanged. Anchor-click and popstate paths continue to work via the existing per-page `useUnsavedGuard`.

---

# Phase A — Scaffolding (no behavior change yet)

Five tasks. Each lands a piece of the new structure but the user-visible behavior on `/settings` is unchanged until Phase B replaces the page body.

## Task A-1: Extend `SettingsDraftContext` with `pendingSection` + `requestSectionChange`

**Files:**
- Modify: `frontend/src/contexts/SettingsDraftContext.tsx`
- Test: `frontend/src/contexts/__tests__/SettingsDraftContext.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/contexts/__tests__/SettingsDraftContext.test.tsx
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  SettingsDraftProvider,
  useSettingsDraftStatus,
} from "@/contexts/SettingsDraftContext";

describe("SettingsDraftContext", () => {
  it("requestSectionChange with isDirty=false navigates immediately (pendingSection stays null)", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <SettingsDraftProvider>{children}</SettingsDraftProvider>
    );
    const { result } = renderHook(() => useSettingsDraftStatus(), { wrapper });
    expect(result.current).not.toBeNull();
    expect(result.current!.pendingSection).toBeNull();
    expect(result.current!.isDirty).toBe(false);

    let navigated: string | null = null;
    act(() => {
      result.current!.requestSectionChange("hr", (dest) => {
        navigated = dest;
      });
    });
    expect(navigated).toBe("/settings/hr");
    expect(result.current!.pendingSection).toBeNull();
  });

  it("requestSectionChange with isDirty=true defers via pendingSection", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <SettingsDraftProvider>{children}</SettingsDraftProvider>
    );
    const { result } = renderHook(() => useSettingsDraftStatus(), { wrapper });

    act(() => result.current!.setDirty(true));
    let navigated: string | null = null;
    act(() => {
      result.current!.requestSectionChange("general", (dest) => {
        navigated = dest;
      });
    });
    expect(navigated).toBeNull();
    expect(result.current!.pendingSection).toBe("general");
  });

  it("clearPendingSection resets to null", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <SettingsDraftProvider>{children}</SettingsDraftProvider>
    );
    const { result } = renderHook(() => useSettingsDraftStatus(), { wrapper });
    act(() => result.current!.setDirty(true));
    act(() =>
      result.current!.requestSectionChange("hr", () => {}),
    );
    expect(result.current!.pendingSection).toBe("hr");
    act(() => result.current!.clearPendingSection());
    expect(result.current!.pendingSection).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `cd frontend && npx vitest run src/contexts/__tests__/SettingsDraftContext.test.tsx`
Expected: FAIL — properties `pendingSection`, `requestSectionChange`, `clearPendingSection` don't exist on the context value yet.

- [ ] **Step 3: Extend the context implementation**

Replace `frontend/src/contexts/SettingsDraftContext.tsx` with:

```tsx
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

export type SettingsSection = "general" | "hr" | "sensors";

interface SettingsDraftStatus {
  isDirty: boolean;
  setDirty: (v: boolean) => void;
  pendingSection: SettingsSection | null;
  /**
   * Request a navigation to a sibling settings section.
   * - If !isDirty: invokes `commit("/settings/<section>")` immediately so the
   *   caller (SubHeader picker) can fire wouter.navigate.
   * - If isDirty: stores `section` in `pendingSection` so the active page
   *   can open its UnsavedChangesDialog. The page is responsible for
   *   calling navigate + clearPendingSection on confirm, or
   *   clearPendingSection alone on cancel.
   */
  requestSectionChange: (
    section: SettingsSection,
    commit: (dest: string) => void,
  ) => void;
  clearPendingSection: () => void;
}

const Ctx = createContext<SettingsDraftStatus | null>(null);

export function SettingsDraftProvider({ children }: { children: ReactNode }) {
  const [isDirty, setDirty] = useState(false);
  const [pendingSection, setPendingSection] = useState<SettingsSection | null>(null);

  const requestSectionChange = useCallback(
    (section: SettingsSection, commit: (dest: string) => void) => {
      if (isDirty) {
        setPendingSection(section);
      } else {
        commit(`/settings/${section}`);
      }
    },
    [isDirty],
  );

  const clearPendingSection = useCallback(() => {
    setPendingSection(null);
  }, []);

  return (
    <Ctx.Provider
      value={{
        isDirty,
        setDirty,
        pendingSection,
        requestSectionChange,
        clearPendingSection,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useSettingsDraftStatus(): SettingsDraftStatus | null {
  return useContext(Ctx);
}
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `cd frontend && npx vitest run src/contexts/__tests__/SettingsDraftContext.test.tsx`
Expected: PASS — 3 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/contexts/SettingsDraftContext.tsx \
        frontend/src/contexts/__tests__/SettingsDraftContext.test.tsx
git commit -m "feat(A-1): SettingsDraftContext — pendingSection + requestSectionChange"
```

---

## Task A-2: `useSettingsSection` hook

**Files:**
- Create: `frontend/src/hooks/useSettingsSection.ts`
- Test: `frontend/src/hooks/__tests__/useSettingsSection.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/hooks/__tests__/useSettingsSection.test.tsx
import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { useSettingsSection } from "@/hooks/useSettingsSection";

function makeWrapper(path: string) {
  const memory = memoryLocation({ path, record: true });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <Router hook={memory.hook}>{children}</Router>
  );
  return { Wrapper, memory };
}

describe("useSettingsSection", () => {
  it("returns 'general' for /settings (the redirect target)", () => {
    const { Wrapper } = makeWrapper("/settings");
    const { result } = renderHook(() => useSettingsSection(), {
      wrapper: Wrapper,
    });
    expect(result.current.section).toBe("general");
  });

  it("returns 'general' for /settings/general", () => {
    const { Wrapper } = makeWrapper("/settings/general");
    const { result } = renderHook(() => useSettingsSection(), {
      wrapper: Wrapper,
    });
    expect(result.current.section).toBe("general");
  });

  it("returns 'hr' for /settings/hr", () => {
    const { Wrapper } = makeWrapper("/settings/hr");
    const { result } = renderHook(() => useSettingsSection(), {
      wrapper: Wrapper,
    });
    expect(result.current.section).toBe("hr");
  });

  it("returns 'sensors' for /settings/sensors", () => {
    const { Wrapper } = makeWrapper("/settings/sensors");
    const { result } = renderHook(() => useSettingsSection(), {
      wrapper: Wrapper,
    });
    expect(result.current.section).toBe("sensors");
  });

  it("returns 'general' for any unknown /settings/<x>", () => {
    const { Wrapper } = makeWrapper("/settings/unknown");
    const { result } = renderHook(() => useSettingsSection(), {
      wrapper: Wrapper,
    });
    expect(result.current.section).toBe("general");
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useSettingsSection.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the hook**

Create `frontend/src/hooks/useSettingsSection.ts` with:

```ts
import { useLocation } from "wouter";
import type { SettingsSection } from "@/contexts/SettingsDraftContext";

const KNOWN: ReadonlySet<SettingsSection> = new Set(["general", "hr", "sensors"]);

interface UseSettingsSectionReturn {
  section: SettingsSection;
}

/**
 * Parse the active settings section from the wouter location.
 * - /settings              → "general" (the redirect target)
 * - /settings/general      → "general"
 * - /settings/hr           → "hr"
 * - /settings/sensors      → "sensors"
 * - /settings/<unknown>    → "general" (defensive — never throws)
 *
 * The picker reads `section` to render the active value. For navigation,
 * callers use `useSettingsDraftStatus().requestSectionChange(...)` directly;
 * this hook intentionally has no `go()` method, keeping it pure.
 */
export function useSettingsSection(): UseSettingsSectionReturn {
  const [path] = useLocation();
  const segs = path.split("/").filter(Boolean); // ["settings"] or ["settings", "<sec>"]
  const candidate = (segs[1] ?? "general") as SettingsSection;
  const section: SettingsSection = KNOWN.has(candidate) ? candidate : "general";
  return { section };
}
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useSettingsSection.test.tsx`
Expected: PASS — 5 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useSettingsSection.ts \
        frontend/src/hooks/__tests__/useSettingsSection.test.tsx
git commit -m "feat(A-2): useSettingsSection — derive active section from URL"
```

---

## Task A-3: `SettingsSectionPicker` component

**Files:**
- Create: `frontend/src/components/SettingsSectionPicker.tsx`
- Test: `frontend/src/components/__tests__/SettingsSectionPicker.test.tsx`
- Modify: `frontend/src/locales/en.json`, `frontend/src/locales/de.json` (4 new keys)

- [ ] **Step 1: Add i18n keys**

In `frontend/src/locales/en.json`, find the `"settings.sensors_link.cta"` block and add the four new keys near the other `settings.*` entries (alphabetical order is fine):

```json
"settings.section.general": "General",
"settings.section.hr": "HR",
"settings.section.sensors": "Sensors",
"settings.section_picker.aria": "Settings section",
```

In `frontend/src/locales/de.json`, the same keys in German:

```json
"settings.section.general": "Allgemein",
"settings.section.hr": "HR",
"settings.section.sensors": "Sensoren",
"settings.section_picker.aria": "Einstellungsbereich",
```

- [ ] **Step 2: Write failing test**

```tsx
// frontend/src/components/__tests__/SettingsSectionPicker.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n";
import { SettingsDraftProvider } from "@/contexts/SettingsDraftContext";
import { SettingsSectionPicker } from "@/components/SettingsSectionPicker";

function renderAt(path: string) {
  const memory = memoryLocation({ path, record: true });
  return {
    memory,
    ...render(
      <I18nextProvider i18n={i18n}>
        <SettingsDraftProvider>
          <Router hook={memory.hook}>
            <SettingsSectionPicker />
          </Router>
        </SettingsDraftProvider>
      </I18nextProvider>,
    ),
  };
}

describe("SettingsSectionPicker", () => {
  beforeEach(() => {
    // Stub fetch so any spurious calls don't break the suite.
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("{}", { status: 200 }),
    );
  });

  it("renders the trigger with data-testid='settings-section-picker-trigger'", () => {
    renderAt("/settings/general");
    expect(
      screen.getByTestId("settings-section-picker-trigger"),
    ).toBeInTheDocument();
  });

  it("trigger shows the translated label for the active section (not the raw id)", () => {
    renderAt("/settings/hr");
    const trigger = screen.getByTestId("settings-section-picker-trigger");
    expect(trigger.textContent ?? "").not.toContain("hr");
    expect(trigger.textContent ?? "").toContain(i18n.t("settings.section.hr"));
  });

  it("selecting an option (clean state) navigates to the matching path", async () => {
    const { memory } = renderAt("/settings/general");
    const trigger = screen.getByTestId("settings-section-picker-trigger");
    await userEvent.click(trigger);
    await userEvent.click(screen.getByRole("option", { name: /HR/i }));
    expect(memory.history).toContain("/settings/hr");
  });
});
```

- [ ] **Step 3: Run the test, confirm it fails**

Run: `cd frontend && npx vitest run src/components/__tests__/SettingsSectionPicker.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 4: Implement the picker**

Create `frontend/src/components/SettingsSectionPicker.tsx` with:

```tsx
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useSettingsDraftStatus,
  type SettingsSection,
} from "@/contexts/SettingsDraftContext";
import { useSettingsSection } from "@/hooks/useSettingsSection";

const SECTIONS: SettingsSection[] = ["general", "hr", "sensors"];

export function SettingsSectionPicker() {
  const { t } = useTranslation();
  const { section } = useSettingsSection();
  const status = useSettingsDraftStatus();
  const [, navigate] = useLocation();

  const labelFor = (s: SettingsSection) => t(`settings.section.${s}`);

  const handleChange = (next: SettingsSection) => {
    // No-op when context is somehow unmounted — treat as a clean navigation.
    if (!status) {
      navigate(`/settings/${next}`);
      return;
    }
    status.requestSectionChange(next, (dest) => navigate(dest));
  };

  return (
    <Select<SettingsSection> value={section} onValueChange={handleChange}>
      <SelectTrigger
        data-testid="settings-section-picker-trigger"
        className="w-40"
        aria-label={t("settings.section_picker.aria")}
      >
        <SelectValue>{labelFor}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {SECTIONS.map((s) => (
          <SelectItem key={s} value={s}>
            {labelFor(s)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
```

- [ ] **Step 5: Run the test, confirm it passes**

Run: `cd frontend && npx vitest run src/components/__tests__/SettingsSectionPicker.test.tsx`
Expected: PASS — 3 tests.

Also run `cd frontend && npm run build` — expect exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/SettingsSectionPicker.tsx \
        frontend/src/components/__tests__/SettingsSectionPicker.test.tsx \
        frontend/src/locales/en.json \
        frontend/src/locales/de.json
git commit -m "feat(A-3): SettingsSectionPicker dropdown + i18n keys"
```

---

## Task A-4: Wire `SettingsSectionPicker` into `SubHeader`

**Files:**
- Modify: `frontend/src/components/SubHeader.tsx`

- [ ] **Step 1: Read the SubHeader file to find the left-cluster block**

Run: `grep -n "isDashboard\|showSignageTabs\|SensorTimeWindow" frontend/src/components/SubHeader.tsx`

You'll find a `<div className="flex items-center gap-3">` containing the `isDashboard && <Toggle>...`, `isDashboard && <DateRangeFilter>...`, `location === "/sensors" && <SensorTimeWindowPicker />`, and `showSignageTabs && <Select>...` branches.

- [ ] **Step 2: Add a Settings-routes branch alongside the others**

Add this branch INSIDE the same left-cluster div, after the `showSignageTabs` branch:

```tsx
{location.startsWith("/settings") && <SettingsSectionPicker />}
```

Add the import near the other `@/components/...` imports at the top of `SubHeader.tsx`:

```tsx
import { SettingsSectionPicker } from "@/components/SettingsSectionPicker";
```

- [ ] **Step 3: Verify build is still clean**

Run: `cd frontend && npm run build`
Expected: exit 0, zero `error TS`.

- [ ] **Step 4: Manually verify in dev (optional but recommended)**

The dev server is bind-mounted; HMR picks up the change. Reload `http://localhost/` and navigate to `/settings/sensors`. The SubHeader should now show a `<Select>` with three options. Selecting "HR" or "Allgemein" will land on `/settings/hr` or `/settings/general` — both still 404 (no route registered yet) until A-5.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SubHeader.tsx
git commit -m "feat(A-4): SubHeader renders SettingsSectionPicker on /settings/*"
```

---

## Task A-5: Register the new wouter routes (placeholder pages)

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Read the existing route block**

Run: `grep -n 'Route path="/settings\|component={SettingsPage}\|SensorsSettingsPage' frontend/src/App.tsx`

Today the routes look like:

```tsx
<Route path="/settings/sensors" component={SensorsSettingsPage} />
<Route path="/settings" component={SettingsPage} />
```

- [ ] **Step 2: Replace with the four routes (Sensors first per first-match-wins)**

Change to:

```tsx
<Route path="/settings/sensors" component={SensorsSettingsPage} />
<Route path="/settings/general" component={GeneralSettingsPage} />
<Route path="/settings/hr" component={HrSettingsPage} />
<Route path="/settings" component={SettingsPage} />
```

`SettingsPage` is intentionally last and stays the catch-all redirect target (Task B-4 turns it into a `<Redirect />`).

- [ ] **Step 3: Add placeholder page imports + minimal stub files**

Create `frontend/src/pages/GeneralSettingsPage.tsx`:

```tsx
export function GeneralSettingsPage() {
  return (
    <div data-testid="settings-page-general" className="max-w-7xl mx-auto px-6 pt-4">
      <h1 className="text-3xl font-semibold">General</h1>
      <p className="text-sm text-muted-foreground">
        Wired in Task B-2 — placeholder for routing scaffold.
      </p>
    </div>
  );
}
```

Create `frontend/src/pages/HrSettingsPage.tsx`:

```tsx
export function HrSettingsPage() {
  return (
    <div data-testid="settings-page-hr" className="max-w-7xl mx-auto px-6 pt-4">
      <h1 className="text-3xl font-semibold">HR</h1>
      <p className="text-sm text-muted-foreground">
        Wired in Task B-3 — placeholder for routing scaffold.
      </p>
    </div>
  );
}
```

Add the imports at the top of `App.tsx` near the other page imports:

```tsx
import { GeneralSettingsPage } from "@/pages/GeneralSettingsPage";
import { HrSettingsPage } from "@/pages/HrSettingsPage";
```

- [ ] **Step 4: Verify build is still clean**

Run: `cd frontend && npm run build`
Expected: exit 0.

- [ ] **Step 5: Manually verify the picker now resolves both new paths**

Reload `http://localhost/`. Navigate to `/settings`. The page should still render today's long-scrolling layout (we haven't replaced it yet — that's Task B-4). Open the SubHeader picker → "Allgemein" → URL becomes `/settings/general`, body shows the placeholder. Same for "HR".

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx \
        frontend/src/pages/GeneralSettingsPage.tsx \
        frontend/src/pages/HrSettingsPage.tsx
git commit -m "feat(A-5): wouter routes for /settings/general + /settings/hr (placeholders)"
```

---

# Phase B — Page split (the actual move)

Replaces placeholder pages with real implementations and turns `/settings` into a redirect.

## Task B-1: Add `slice` parameter to `useSettingsDraft`

**Files:**
- Modify: `frontend/src/hooks/useSettingsDraft.ts`
- Test: extend or create `frontend/src/hooks/__tests__/useSettingsDraft.slice.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/hooks/__tests__/useSettingsDraft.slice.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useSettingsDraft } from "@/hooks/useSettingsDraft";

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const SETTINGS_RESPONSE = {
  color_primary: "oklch(0.55 0.15 250)",
  color_accent: "oklch(0.70 0.18 150)",
  color_background: "oklch(1.00 0 0)",
  color_foreground: "oklch(0.15 0 0)",
  color_muted: "oklch(0.90 0 0)",
  color_destructive: "oklch(0.55 0.22 25)",
  app_name: "X",
  logo_url: null,
  logo_updated_at: null,
  personio_has_credentials: false,
  personio_sync_interval_h: 168,
  personio_sick_leave_type_id: [],
  personio_production_dept: [],
  personio_skill_attr_key: [],
  target_overtime_ratio: null,
  target_sick_leave_ratio: null,
  target_fluctuation: null,
  target_revenue_per_employee: null,
  sensor_poll_interval_s: 60,
  sensor_temperature_min: null,
  sensor_temperature_max: null,
  sensor_humidity_min: null,
  sensor_humidity_max: null,
};

describe("useSettingsDraft slice", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/settings")) {
        return new Response(JSON.stringify(SETTINGS_RESPONSE), { status: 200 });
      }
      return new Response("{}", { status: 200 });
    });
  });

  it("slice='general' isDirty stays false when an HR field changes", async () => {
    const Wrapper = makeWrapper();
    const { result } = renderHook(
      () => useSettingsDraft({ slice: "general" }),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(result.current.draft).not.toBeNull());

    act(() =>
      result.current.setField("personio_sync_interval_h", 24),
    );
    expect(result.current.isDirty).toBe(false);
  });

  it("slice='general' isDirty becomes true when a color field changes", async () => {
    const Wrapper = makeWrapper();
    const { result } = renderHook(
      () => useSettingsDraft({ slice: "general" }),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(result.current.draft).not.toBeNull());

    act(() => result.current.setField("color_primary", "#ff0000"));
    expect(result.current.isDirty).toBe(true);
  });

  it("slice='hr' isDirty stays false when a color field changes", async () => {
    const Wrapper = makeWrapper();
    const { result } = renderHook(
      () => useSettingsDraft({ slice: "hr" }),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(result.current.draft).not.toBeNull());

    act(() => result.current.setField("color_primary", "#ff0000"));
    expect(result.current.isDirty).toBe(false);
  });

  it("slice='hr' isDirty becomes true when a Personio field changes", async () => {
    const Wrapper = makeWrapper();
    const { result } = renderHook(
      () => useSettingsDraft({ slice: "hr" }),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(result.current.draft).not.toBeNull());

    act(() => result.current.setField("personio_sync_interval_h", 24));
    expect(result.current.isDirty).toBe(true);
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useSettingsDraft.slice.test.tsx`
Expected: FAIL — `useSettingsDraft({ slice: ... })` doesn't accept arguments yet (signature mismatch + isDirty doesn't honor the slice).

- [ ] **Step 3: Add the `slice` parameter and slice-aware dirty/diff logic**

Edit `frontend/src/hooks/useSettingsDraft.ts`. Near the top, add the slice constants and helper:

```ts
export type SettingsSlice = "general" | "hr";

const GENERAL_FIELDS = [
  "app_name",
  "color_primary",
  "color_accent",
  "color_background",
  "color_foreground",
  "color_muted",
  "color_destructive",
] as const satisfies readonly (keyof DraftFields)[];

const HR_FIELDS = [
  "personio_client_id",
  "personio_client_secret",
  "personio_sync_interval_h",
  "personio_sick_leave_type_id",
  "personio_production_dept",
  "personio_skill_attr_key",
  "target_overtime_ratio",
  "target_sick_leave_ratio",
  "target_fluctuation",
  "target_revenue_per_employee",
] as const satisfies readonly (keyof DraftFields)[];

function fieldsForSlice(slice: SettingsSlice): readonly (keyof DraftFields)[] {
  return slice === "general" ? GENERAL_FIELDS : HR_FIELDS;
}

function eqField<K extends keyof DraftFields>(
  key: K,
  a: DraftFields[K],
  b: DraftFields[K],
): boolean {
  if (Array.isArray(a) && Array.isArray(b)) {
    return JSON.stringify(a) === JSON.stringify(b);
  }
  return a === b;
}

function sliceIsDirty(
  draft: DraftFields,
  snapshot: DraftFields,
  slice: SettingsSlice,
): boolean {
  for (const k of fieldsForSlice(slice)) {
    if (!eqField(k, draft[k], snapshot[k])) return true;
  }
  return false;
}
```

Update the hook signature to accept and honor `slice`:

```ts
interface UseSettingsDraftOptions {
  slice: SettingsSlice;
}

export function useSettingsDraft(opts: UseSettingsDraftOptions): UseSettingsDraftReturn {
  const { slice } = opts;
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useSettings();
  const [snapshot, setSnapshot] = useState<DraftFields | null>(null);
  const [draft, setDraft] = useState<DraftFields | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // ... existing useEffect for snapshot capture stays unchanged ...

  const isDirty = useMemo(() => {
    if (!draft || !snapshot) return false;
    return sliceIsDirty(draft, snapshot, slice);
  }, [draft, snapshot, slice]);

  // setField, save, discard, resetToDefaults stay as-is — they operate on
  // the full DraftFields shape. PUT payloads still send all fields the user
  // could have changed; the backend SettingsUpdate model accepts partial
  // updates (every field is Optional). The slice purely scopes `isDirty`,
  // which gates the UnsavedChangesDialog and the ActionBar's Save button.

  // ... rest of the hook unchanged ...
}
```

(Leave the `shallowEqualDraft`-based path intact — it's used by `discard` indirectly via the snapshot copy, no behavioural change.)

- [ ] **Step 4: Run the test, confirm it passes**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useSettingsDraft.slice.test.tsx`
Expected: PASS — 4 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useSettingsDraft.ts \
        frontend/src/hooks/__tests__/useSettingsDraft.slice.test.tsx
git commit -m "feat(B-1): useSettingsDraft accepts {slice} and scopes isDirty"
```

---

## Task B-2: `GeneralSettingsPage` (real implementation)

**Files:**
- Modify: `frontend/src/pages/GeneralSettingsPage.tsx` (replace placeholder)
- Test: `frontend/src/pages/__tests__/GeneralSettingsPage.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/pages/__tests__/GeneralSettingsPage.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { I18nextProvider } from "react-i18next";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18n from "@/i18n";
import { SettingsDraftProvider } from "@/contexts/SettingsDraftContext";
import { GeneralSettingsPage } from "@/pages/GeneralSettingsPage";

vi.mock("@/auth/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "tester@example.com", role: "admin" },
    signOut: vi.fn(),
  }),
}));

const SETTINGS_RESPONSE = {
  color_primary: "oklch(0.55 0.15 250)",
  color_accent: "oklch(0.70 0.18 150)",
  color_background: "oklch(1.00 0 0)",
  color_foreground: "oklch(0.15 0 0)",
  color_muted: "oklch(0.90 0 0)",
  color_destructive: "oklch(0.55 0.22 25)",
  app_name: "Test",
  logo_url: null,
  logo_updated_at: null,
  personio_has_credentials: false,
  personio_sync_interval_h: 168,
  personio_sick_leave_type_id: [],
  personio_production_dept: [],
  personio_skill_attr_key: [],
  target_overtime_ratio: null,
  target_sick_leave_ratio: null,
  target_fluctuation: null,
  target_revenue_per_employee: null,
  sensor_poll_interval_s: 60,
  sensor_temperature_min: null,
  sensor_temperature_max: null,
  sensor_humidity_min: null,
  sensor_humidity_max: null,
};

function renderPage() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.endsWith("/api/settings")) {
      return new Response(JSON.stringify(SETTINGS_RESPONSE), { status: 200 });
    }
    return new Response("{}", { status: 200 });
  });
  const memory = memoryLocation({ path: "/settings/general", record: true });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>
        <SettingsDraftProvider>
          <Router hook={memory.hook}>
            <GeneralSettingsPage />
          </Router>
        </SettingsDraftProvider>
      </I18nextProvider>
    </QueryClientProvider>,
  );
}

describe("GeneralSettingsPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renders with data-testid='settings-page-general'", () => {
    renderPage();
    expect(screen.getByTestId("settings-page-general")).toBeInTheDocument();
  });

  it("renders the app_name input", async () => {
    renderPage();
    // Wait for the settings GET to resolve and the draft to populate.
    expect(await screen.findByLabelText(/app name|app-name/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `cd frontend && npx vitest run src/pages/__tests__/GeneralSettingsPage.test.tsx`
Expected: FAIL — `app_name` input is in the placeholder, not the real page.

- [ ] **Step 3: Implement the real page**

Replace `frontend/src/pages/GeneralSettingsPage.tsx` with:

```tsx
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { toast } from "sonner";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSettings } from "@/hooks/useSettings";
import { useSettingsDraft } from "@/hooks/useSettingsDraft";
import { useUnsavedGuard } from "@/hooks/useUnsavedGuard";
import { hexToOklch, WHITE_OKLCH } from "@/lib/color";
import { ColorPicker } from "@/components/settings/ColorPicker";
import { ContrastBadge } from "@/components/settings/ContrastBadge";
import { LogoUpload } from "@/components/settings/LogoUpload";
import { ActionBar } from "@/components/settings/ActionBar";
import { ResetDialog } from "@/components/settings/ResetDialog";
import { UnsavedChangesDialog } from "@/components/settings/UnsavedChangesDialog";
import { useSettingsDraftStatus } from "@/contexts/SettingsDraftContext";

const SCOPE_PATH = "/settings/general";

function safeHexToOklch(hex: string): string | null {
  try { return hexToOklch(hex); } catch { return null; }
}

export function GeneralSettingsPage() {
  const { t } = useTranslation();
  const [, navigate] = useLocation();
  const { data: settingsData } = useSettings();
  const draftCtx = useSettingsDraftStatus();
  const {
    draft,
    isDirty,
    isLoading,
    isError,
    isSaving,
    setField,
    save,
    discard,
    resetToDefaults,
  } = useSettingsDraft({ slice: "general" });

  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [unsavedDialogOpen, setUnsavedDialogOpen] = useState(false);
  const [pendingNav, setPendingNav] = useState<string | null>(null);

  // Publish dirty state to context so the picker knows whether to defer.
  useEffect(() => {
    draftCtx?.setDirty(isDirty);
  }, [draftCtx, isDirty]);

  // Watch for picker-driven navigation requests.
  useEffect(() => {
    if (!draftCtx?.pendingSection) return;
    setPendingNav(`/settings/${draftCtx.pendingSection}`);
    setUnsavedDialogOpen(true);
  }, [draftCtx?.pendingSection]);

  const handleStay = useCallback(() => {
    setUnsavedDialogOpen(false);
    setPendingNav(null);
    draftCtx?.clearPendingSection();
  }, [draftCtx]);

  const handleDiscardAndLeave = useCallback(() => {
    discard();
    setUnsavedDialogOpen(false);
    const dest = pendingNav;
    setPendingNav(null);
    draftCtx?.clearPendingSection();
    if (dest && dest !== "__back__") navigate(dest);
    if (dest === "__back__") window.history.back();
  }, [discard, navigate, pendingNav, draftCtx]);

  // Anchor-click + popstate guard (existing behavior).
  const handleShowDialog = useCallback((to: string) => {
    setPendingNav(to);
    setUnsavedDialogOpen(true);
  }, []);
  useUnsavedGuard(isDirty, handleShowDialog, SCOPE_PATH);

  const handleSave = useCallback(async () => {
    try {
      await save();
      toast.success(t("settings.toast.saved"));
    } catch (err) {
      toast.error((err as Error).message ?? t("settings.toast.save_failed"));
    }
  }, [save, t]);

  const handleResetConfirm = useCallback(async () => {
    try {
      await resetToDefaults();
      setResetDialogOpen(false);
      toast.success(t("settings.toast.reset"));
    } catch (err) {
      toast.error((err as Error).message ?? t("settings.toast.reset_failed"));
    }
  }, [resetToDefaults, t]);

  if (isError) return <div className="p-6 text-destructive">{t("settings.load_error")}</div>;
  if (isLoading || !draft) return <div className="p-6">{t("common.loading")}</div>;

  const primaryFg =
    safeHexToOklch(draft.color_foreground) ?? draft.color_foreground;

  return (
    <div
      data-testid="settings-page-general"
      className="max-w-7xl mx-auto px-6 pt-4 pb-32 space-y-8"
    >
      <header className="mb-12">
        <h1 className="text-3xl font-semibold leading-tight">
          {t("settings.section.general")}
        </h1>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-xl font-semibold">
            {t("settings.identity.title")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-6 gap-6">
            <div className="flex flex-col gap-2 md:col-span-2">
              <Label htmlFor="app-name" className="text-sm font-medium">
                {t("settings.identity.app_name.label")}
              </Label>
              <Input
                id="app-name"
                value={draft.app_name}
                onChange={(e) => setField("app_name", e.target.value)}
                placeholder={t("settings.identity.app_name.placeholder")}
              />
              <p className="text-xs text-muted-foreground">
                {t("settings.identity.app_name.help")}
              </p>
            </div>
            <div className="flex flex-col gap-2 md:col-span-4">
              <Label className="text-sm font-medium">
                {t("settings.identity.logo.label")}
              </Label>
              <LogoUpload logoUrl={settingsData?.logo_url ?? null} />
            </div>
          </div>

          <hr className="border-border" />

          <section className="space-y-4">
            <h3 className="text-base font-semibold">{t("settings.colors.title")}</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              <ColorPicker
                label={t("settings.colors.primary")}
                value={draft.color_primary}
                onChange={(hex) => setField("color_primary", hex)}
                contrastBadge={
                  <ContrastBadge
                    colorA={safeHexToOklch(draft.color_primary)}
                    colorB={primaryFg}
                  />
                }
              />
              <ColorPicker
                label={t("settings.colors.accent")}
                value={draft.color_accent}
                onChange={(hex) => setField("color_accent", hex)}
              />
              <ColorPicker
                label={t("settings.colors.background")}
                value={draft.color_background}
                onChange={(hex) => setField("color_background", hex)}
                contrastBadge={
                  <ContrastBadge
                    colorA={draft.color_background}
                    colorB={draft.color_foreground}
                  />
                }
              />
              <ColorPicker
                label={t("settings.colors.foreground")}
                value={draft.color_foreground}
                onChange={(hex) => setField("color_foreground", hex)}
                contrastBadge={
                  <ContrastBadge
                    colorA={draft.color_foreground}
                    colorB={draft.color_background}
                  />
                }
              />
              <ColorPicker
                label={t("settings.colors.muted")}
                value={draft.color_muted}
                onChange={(hex) => setField("color_muted", hex)}
              />
              <ColorPicker
                label={t("settings.colors.destructive")}
                value={draft.color_destructive}
                onChange={(hex) => setField("color_destructive", hex)}
                contrastBadge={
                  <ContrastBadge
                    colorA={safeHexToOklch(draft.color_destructive)}
                    colorB={WHITE_OKLCH}
                  />
                }
              />
            </div>
          </section>
        </CardContent>
      </Card>

      <ActionBar
        isDirty={isDirty}
        isSaving={isSaving}
        onSave={handleSave}
        onDiscard={discard}
        onResetClick={() => setResetDialogOpen(true)}
      />

      <ResetDialog
        open={resetDialogOpen}
        onOpenChange={setResetDialogOpen}
        onConfirm={handleResetConfirm}
        isPending={isSaving}
      />

      <UnsavedChangesDialog
        open={unsavedDialogOpen}
        onOpenChange={(open) => {
          if (!open) handleStay();
        }}
        onStay={handleStay}
        onDiscardAndLeave={handleDiscardAndLeave}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `cd frontend && npx vitest run src/pages/__tests__/GeneralSettingsPage.test.tsx`
Expected: PASS — 2 tests.

Also run `cd frontend && npm run build` — expect exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/GeneralSettingsPage.tsx \
        frontend/src/pages/__tests__/GeneralSettingsPage.test.tsx
git commit -m "feat(B-2): GeneralSettingsPage — identity + colors slice"
```

---

## Task B-3: `HrSettingsPage` (real implementation)

**Files:**
- Modify: `frontend/src/pages/HrSettingsPage.tsx` (replace placeholder)
- Test: `frontend/src/pages/__tests__/HrSettingsPage.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/pages/__tests__/HrSettingsPage.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { I18nextProvider } from "react-i18next";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18n from "@/i18n";
import { SettingsDraftProvider } from "@/contexts/SettingsDraftContext";
import { HrSettingsPage } from "@/pages/HrSettingsPage";

vi.mock("@/auth/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "tester@example.com", role: "admin" },
    signOut: vi.fn(),
  }),
}));

const SETTINGS_RESPONSE = {
  color_primary: "oklch(0.55 0.15 250)",
  color_accent: "oklch(0.70 0.18 150)",
  color_background: "oklch(1.00 0 0)",
  color_foreground: "oklch(0.15 0 0)",
  color_muted: "oklch(0.90 0 0)",
  color_destructive: "oklch(0.55 0.22 25)",
  app_name: "Test",
  logo_url: null,
  logo_updated_at: null,
  personio_has_credentials: false,
  personio_sync_interval_h: 168,
  personio_sick_leave_type_id: [],
  personio_production_dept: [],
  personio_skill_attr_key: [],
  target_overtime_ratio: null,
  target_sick_leave_ratio: null,
  target_fluctuation: null,
  target_revenue_per_employee: null,
  sensor_poll_interval_s: 60,
  sensor_temperature_min: null,
  sensor_temperature_max: null,
  sensor_humidity_min: null,
  sensor_humidity_max: null,
};

function renderPage() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.endsWith("/api/settings")) {
      return new Response(JSON.stringify(SETTINGS_RESPONSE), { status: 200 });
    }
    return new Response("{}", { status: 200 });
  });
  const memory = memoryLocation({ path: "/settings/hr", record: true });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>
        <SettingsDraftProvider>
          <Router hook={memory.hook}>
            <HrSettingsPage />
          </Router>
        </SettingsDraftProvider>
      </I18nextProvider>
    </QueryClientProvider>,
  );
}

describe("HrSettingsPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renders with data-testid='settings-page-hr'", () => {
    renderPage();
    expect(screen.getByTestId("settings-page-hr")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `cd frontend && npx vitest run src/pages/__tests__/HrSettingsPage.test.tsx`
Expected: FAIL — placeholder has no Personio card markers.

- [ ] **Step 3: Implement the real page**

Replace `frontend/src/pages/HrSettingsPage.tsx` with:

```tsx
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { toast } from "sonner";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useSettings } from "@/hooks/useSettings";
import { useSettingsDraft } from "@/hooks/useSettingsDraft";
import { useUnsavedGuard } from "@/hooks/useUnsavedGuard";
import { PersonioCard } from "@/components/settings/PersonioCard";
import { HrTargetsCard } from "@/components/settings/HrTargetsCard";
import { ActionBar } from "@/components/settings/ActionBar";
import { ResetDialog } from "@/components/settings/ResetDialog";
import { UnsavedChangesDialog } from "@/components/settings/UnsavedChangesDialog";
import { useSettingsDraftStatus } from "@/contexts/SettingsDraftContext";

const SCOPE_PATH = "/settings/hr";

export function HrSettingsPage() {
  const { t } = useTranslation();
  const [, navigate] = useLocation();
  const { data: settingsData } = useSettings();
  const draftCtx = useSettingsDraftStatus();
  const {
    draft,
    isDirty,
    isLoading,
    isError,
    isSaving,
    setField,
    save,
    discard,
    resetToDefaults,
  } = useSettingsDraft({ slice: "hr" });

  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [unsavedDialogOpen, setUnsavedDialogOpen] = useState(false);
  const [pendingNav, setPendingNav] = useState<string | null>(null);

  useEffect(() => {
    draftCtx?.setDirty(isDirty);
  }, [draftCtx, isDirty]);

  useEffect(() => {
    if (!draftCtx?.pendingSection) return;
    setPendingNav(`/settings/${draftCtx.pendingSection}`);
    setUnsavedDialogOpen(true);
  }, [draftCtx?.pendingSection]);

  const handleStay = useCallback(() => {
    setUnsavedDialogOpen(false);
    setPendingNav(null);
    draftCtx?.clearPendingSection();
  }, [draftCtx]);

  const handleDiscardAndLeave = useCallback(() => {
    discard();
    setUnsavedDialogOpen(false);
    const dest = pendingNav;
    setPendingNav(null);
    draftCtx?.clearPendingSection();
    if (dest && dest !== "__back__") navigate(dest);
    if (dest === "__back__") window.history.back();
  }, [discard, navigate, pendingNav, draftCtx]);

  const handleShowDialog = useCallback((to: string) => {
    setPendingNav(to);
    setUnsavedDialogOpen(true);
  }, []);
  useUnsavedGuard(isDirty, handleShowDialog, SCOPE_PATH);

  const handleSave = useCallback(async () => {
    try {
      await save();
      toast.success(t("settings.toast.saved"));
    } catch (err) {
      toast.error((err as Error).message ?? t("settings.toast.save_failed"));
    }
  }, [save, t]);

  const handleResetConfirm = useCallback(async () => {
    try {
      await resetToDefaults();
      setResetDialogOpen(false);
      toast.success(t("settings.toast.reset"));
    } catch (err) {
      toast.error((err as Error).message ?? t("settings.toast.reset_failed"));
    }
  }, [resetToDefaults, t]);

  if (isError) return <div className="p-6 text-destructive">{t("settings.load_error")}</div>;
  if (isLoading || !draft) return <div className="p-6">{t("common.loading")}</div>;

  return (
    <div
      data-testid="settings-page-hr"
      className="max-w-7xl mx-auto px-6 pt-4 pb-32 space-y-8"
    >
      <header className="mb-12">
        <h1 className="text-3xl font-semibold leading-tight">
          {t("settings.section.hr")}
        </h1>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-xl font-semibold">{t("settings.hr.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-8">
          <PersonioCard
            draft={draft}
            setField={setField}
            hasCredentials={settingsData?.personio_has_credentials ?? false}
            embedded
          />
          <hr className="border-border" />
          <HrTargetsCard draft={draft} setField={setField} embedded />
        </CardContent>
      </Card>

      <ActionBar
        isDirty={isDirty}
        isSaving={isSaving}
        onSave={handleSave}
        onDiscard={discard}
        onResetClick={() => setResetDialogOpen(true)}
      />

      <ResetDialog
        open={resetDialogOpen}
        onOpenChange={setResetDialogOpen}
        onConfirm={handleResetConfirm}
        isPending={isSaving}
      />

      <UnsavedChangesDialog
        open={unsavedDialogOpen}
        onOpenChange={(open) => {
          if (!open) handleStay();
        }}
        onStay={handleStay}
        onDiscardAndLeave={handleDiscardAndLeave}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `cd frontend && npx vitest run src/pages/__tests__/HrSettingsPage.test.tsx`
Expected: PASS — 1 test.

Also run `cd frontend && npm run build` — expect exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/HrSettingsPage.tsx \
        frontend/src/pages/__tests__/HrSettingsPage.test.tsx
git commit -m "feat(B-3): HrSettingsPage — Personio + HR targets slice"
```

---

## Task B-4: Replace `SettingsPage` with a redirect

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Test: `frontend/src/pages/__tests__/SettingsPage.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/pages/__tests__/SettingsPage.test.tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { SettingsPage } from "@/pages/SettingsPage";

describe("SettingsPage (redirect)", () => {
  it("renders nothing of its own and redirects to /settings/general", () => {
    const memory = memoryLocation({ path: "/settings", record: true });
    render(
      <Router hook={memory.hook}>
        <SettingsPage />
      </Router>,
    );
    // wouter <Redirect> updates the location synchronously on first render.
    expect(memory.history).toContain("/settings/general");
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `cd frontend && npx vitest run src/pages/__tests__/SettingsPage.test.tsx`
Expected: FAIL — current SettingsPage renders the long-scrolling page, doesn't navigate.

- [ ] **Step 3: Replace the page body**

Replace `frontend/src/pages/SettingsPage.tsx` with:

```tsx
import { Redirect } from "wouter";

/**
 * Bare /settings is a redirect to /settings/general (v1.28). The body that
 * used to live here was extracted into GeneralSettingsPage + HrSettingsPage
 * and the link to the Sensors page is now implicit via the SubHeader picker.
 *
 * Kept as a named export at this path so existing imports (App.tsx route
 * registration) and bookmarks to `/settings` continue to work.
 */
export function SettingsPage() {
  return <Redirect to="/settings/general" />;
}
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `cd frontend && npx vitest run src/pages/__tests__/SettingsPage.test.tsx`
Expected: PASS — 1 test.

Also run `cd frontend && npm run build` — expect exit 0. Imports of `useSettings`, `useSettingsDraft`, etc. are now gone from this file; if any import is unused elsewhere as a result, vitest's strict TS will flag it. (The existing `DraftFields` import in PersonioCard / HrTargetsCard still resolves — no change.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx \
        frontend/src/pages/__tests__/SettingsPage.test.tsx
git commit -m "feat(B-4): SettingsPage retired to <Redirect to=\"/settings/general\" />"
```

---

# Phase C — Verification + ship

## Task C-1: Full vitest pass

- [ ] **Step 1: Run the entire frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: all green. No new failures vs. the v1.27 baseline (255 passed, 1 skipped). The new tests from A-1, A-2, A-3, B-1, B-2, B-3, B-4 add ~15 more passing tests.

- [ ] **Step 2: If anything fails, fix it. Otherwise proceed.**

Likely culprits if a regression slipped in:
- The old SettingsPage tests (if any) referenced fields the new redirect doesn't render — delete or rewrite them.
- `useSettingsDraft` callers that didn't pass `slice` — TypeScript would have caught these in `npm run build` already; if vitest catches one, add the argument.

---

## Task C-2: Acceptance — `pytest -q` + `npm run build` green

- [ ] **Step 1: Backend smoke (no backend changes, baseline preserved)**

Run: `docker compose exec -T api pytest -q`
Expected: 366 passed, 6 skipped, 59 deselected (matches the v1.27 baseline). No new failures.

- [ ] **Step 2: Frontend build**

Run: `cd frontend && npm run build`
Expected: exit 0, zero `error TS`.

- [ ] **Step 3: Manual mobile-emulation acceptance check**

Open `http://localhost/settings` in Chrome with DevTools mobile emulation set to **iPhone 13** (390×844). Verify:

- `/settings` redirects to `/settings/general`. The URL bar updates.
- The SubHeader shows a `<Select>` displaying "Allgemein" with three options ("Allgemein" / "HR" / "Sensoren").
- Selecting "HR" navigates to `/settings/hr`. The body re-renders with the Personio + HR targets card.
- Editing the Personio "Sync interval" then selecting "Allgemein" pops the `UnsavedChangesDialog`. "Stay" cancels; "Discard and leave" navigates and discards.
- Selecting "Sensoren" navigates to `/settings/sensors` (existing page, no functional change).
- At ≥ 768 px the SubHeader picker is the same `<Select>` (the v1.25 dual-render isn't needed because base-ui Select already works at all viewport widths). Confirm the picker fits the SubHeader's 12 px row without overflow.

If any item fails, file a follow-up commit before C-3.

---

## Task C-3: Ship commit

- [ ] **Step 1: Update README version-history table**

Append above the v1.27 row (`README.md` near the top of the version table):

```markdown
| v1.28 | 2026-05-01 | Settings restructure — peer pages with SubHeader dropdown nav. The single long-scrolling `/settings` page split into `/settings/general` (app_name + logo + 6 colors) and `/settings/hr` (Personio + targets); `/settings/sensors` unchanged. `/settings` is now a `<Redirect to="/settings/general">`. A new `SettingsSectionPicker` `<Select>` lives in the SubHeader on `/settings/*` and is the only navigation between sections. Each page owns its own draft slice via `useSettingsDraft({ slice })`; the `UnsavedChangesDialog` from v1.25 is reused for picker-driven, anchor-click, and popstate navigations. `SettingsDraftContext` was extended with `pendingSection` + `requestSectionChange` so the picker (which lives outside the page tree) can defer a programmatic navigation when the active page is dirty. |
```

- [ ] **Step 2: Commit the README update**

```bash
git add README.md
git commit -m "docs(v1.28): add Settings peer-pages restructure to version history"
```

- [ ] **Step 3: Empty tag commit**

```bash
git commit --allow-empty -m "$(cat <<'EOF'
chore: v1.28 Settings peer-pages restructure complete

Verification (all green):
  - cd frontend && npx vitest run → all suites pass, +~15 new tests
  - cd frontend && npm run build → exit 0, zero TS errors
  - docker compose exec api pytest -q → 366 passed (v1.27 baseline)
  - manual 390×844 mobile emulation: redirect, dropdown nav, dirty-guard,
    sensor passthrough all verified per plan C-2 step 3

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

- Spec coverage:
  - Routes: 3 peer routes + redirect → A-5 + B-4.
  - SettingsSectionPicker → A-3 (component + i18n keys).
  - useSettingsSection → A-2.
  - SubHeader change → A-4.
  - GeneralSettingsPage → B-2.
  - HrSettingsPage → B-3.
  - useSettingsDraft slice param → B-1.
  - SettingsRedirect → B-4 (kept as the same file; renamed in spirit only).
  - Locale parity (4 keys × 2 languages) → A-3.
- Spec correction: spec said `useUnsavedGuard already hooks into wouter location changes`. Plan corrects this: programmatic navigations from the picker are routed through `SettingsDraftContext.requestSectionChange` → `pendingSection` → page-level dialog. The existing `useUnsavedGuard` continues to handle anchor clicks + popstate + beforeunload unchanged.
- Type consistency: `SettingsSection` defined once in `SettingsDraftContext`, imported by `useSettingsSection`, `SettingsSectionPicker`. `SettingsSlice` defined in `useSettingsDraft` (subset: `"general" | "hr"` — no `"sensors"` because that page uses a separate draft hook).
- Acceptance tests in C-2 step 3 cover spec § Acceptance.
- No backend changes — `pytest -q` baseline preserved.
- Out-of-scope items from the spec (lazy loading, top-level Sensors path, splitting SettingsUpdate by slice, Sensors-into-shared-draft) are not addressed in any task.
