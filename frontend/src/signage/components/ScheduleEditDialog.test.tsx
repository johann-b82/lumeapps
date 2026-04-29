import * as React from "react";
import { describe, test, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";

import i18n from "@/i18n";
import { ScheduleEditDialog } from "./ScheduleEditDialog";

// Mock the API module before imports resolve it.
vi.mock("@/signage/lib/signageApi", () => ({
  signageApi: {
    listPlaylists: vi.fn(async () => [
      { id: "p1", name: "PL", description: null, enabled: true, priority: 0, tag_ids: null, created_at: "2026-01-01", updated_at: "2026-01-01" },
    ]),
    createSchedule: vi.fn(async (body: unknown) => ({
      id: "s-new",
      ...(body as Record<string, unknown>),
      created_at: "x",
      updated_at: "x",
    })),
    updateSchedule: vi.fn(async (id: string, body: unknown) => ({
      id,
      ...(body as Record<string, unknown>),
      created_at: "x",
      updated_at: "x",
    })),
  },
  ApiErrorWithBody: class ApiErrorWithBody extends Error {
    status = 0;
    body: unknown = null;
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

// Plan 55-05 migration: the component now uses base-ui Select, whose popup
// cannot be opened via fireEvent/user-event in jsdom (backdrop intercepts
// pointer events — same limitation documented in 55-02-SUMMARY). We substitute
// a native <select> shim so existing tests (which drive the playlist dropdown
// via fireEvent.change) continue to exercise the same behaviour. This mirrors
// the "test fixture raw <select>" carve-out noted in Phase 55 RESEARCH.
vi.mock("@/components/ui/select", () => {
  // React is imported as a module namespace at the top of this file; the
  // factory closes over it at mock-resolution time (Phase 61 cleanup: bare
  // require() is not type-safe under erasableSyntaxOnly + no @types/node).
  type TriggerProps = Record<string, unknown>;
  const CtxRoot = React.createContext<{
    value?: string;
    onValueChange?: (v: string) => void;
    triggerRef?: { current: TriggerProps };
  }>({});
  function Select({
    value,
    onValueChange,
    children,
  }: {
    value?: string;
    onValueChange?: (v: string) => void;
    children?: React.ReactNode;
  }) {
    const triggerRef = React.useRef<TriggerProps>({});
    return React.createElement(
      CtxRoot.Provider,
      { value: { value, onValueChange, triggerRef } },
      children,
    );
  }
  function SelectTrigger({
    children,
    ...rest
  }: {
    children?: React.ReactNode;
    [k: string]: unknown;
  }) {
    const root = React.useContext(CtxRoot);
    if (root.triggerRef) root.triggerRef.current = rest;
    return React.createElement(React.Fragment, null, children);
  }
  function SelectValue() {
    return null;
  }
  function SelectContent({ children }: { children?: React.ReactNode }) {
    const root = React.useContext(CtxRoot);
    const trigger = root.triggerRef?.current ?? {};
    return React.createElement(
      "select",
      {
        "data-slot": "select-native-shim",
        value: root.value ?? "",
        onChange: (e: React.ChangeEvent<HTMLSelectElement>) =>
          root.onValueChange?.(e.target.value),
        ...trigger,
      },
      React.createElement("option", { value: "" }, ""),
      children,
    );
  }
  function SelectItem({
    value,
    children,
  }: {
    value: string;
    children?: React.ReactNode;
  }) {
    return React.createElement("option", { value }, children);
  }
  return {
    Select,
    SelectTrigger,
    SelectValue,
    SelectContent,
    SelectItem,
    SelectGroup: ({ children }: { children?: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    SelectGroupLabel: ({ children }: { children?: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    SelectSeparator: () => null,
  };
});

import { signageApi } from "@/signage/lib/signageApi";

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <I18nextProvider i18n={i18n}>{ui}</I18nextProvider>
      </QueryClientProvider>,
    ),
  };
}

async function waitForPlaylistLoaded() {
  // The <select> hydrates once listPlaylists resolves.
  await waitFor(() => {
    expect(screen.getByRole("option", { name: "PL" })).toBeInTheDocument();
  });
}

// Helpers: base-ui Checkbox renders role="checkbox" (span with aria-checked);
// we also render a <span> with the visible text inside the <label>. The
// weekday checkbox is the ONE with role="checkbox" whose accessible name
// matches the weekday abbreviation.
function getDayCheckbox(label: string): HTMLElement {
  return screen.getByRole("checkbox", { name: label });
}
function isChecked(el: HTMLElement): boolean {
  return el.getAttribute("aria-checked") === "true";
}
function getSelect(): HTMLSelectElement {
  return screen.getByRole("combobox") as HTMLSelectElement;
}

// Concrete translations from en.json that we assert on.
const T = {
  playlist_required: "Choose a playlist.",
  weekdays_required: "Pick at least one weekday.",
  time_format: "Use HH:MM (00:00 to 23:59).",
  start_equals_end: "Start and end time must differ.",
  midnight_span:
    "Keep the window within one day. Split midnight-spanning ranges into two schedules.",
  start_after_end: "Start time must be before end time.",
  create_cta: "Create schedule",
  quickpick_weekdays: "Weekdays",
  quickpick_weekend: "Weekend",
  quickpick_daily: "Daily",
};

describe("ScheduleEditDialog — validation + quick-picks (D-12, D-05, D-11)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    i18n.changeLanguage("en");
  });

  test("submits with empty form — surfaces all required errors", async () => {
    renderWithProviders(
      <ScheduleEditDialog open onOpenChange={() => {}} schedule={null} />,
    );
    await waitForPlaylistLoaded();

    const submit = screen.getByRole("button", { name: T.create_cta });
    fireEvent.click(submit);

    expect(await screen.findByText(T.playlist_required)).toBeInTheDocument();
    expect(screen.getByText(T.weekdays_required)).toBeInTheDocument();
    // Empty times -> time_format (decision tree short-circuits before equal/reversal).
    expect(screen.getByText(T.time_format)).toBeInTheDocument();
    expect(signageApi.createSchedule).not.toHaveBeenCalled();
  });

  test("time decision tree: start === end -> start_equals_end (NOT midnight_span, NOT start_after_end)", async () => {
    renderWithProviders(
      <ScheduleEditDialog open onOpenChange={() => {}} schedule={null} />,
    );
    await waitForPlaylistLoaded();

    fireEvent.change(getSelect(), {
      target: { value: "p1" },
    });
    // Monday checkbox
    fireEvent.click(getDayCheckbox("Mon"));
    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "09:00" },
    });
    fireEvent.change(screen.getByLabelText("End time"), {
      target: { value: "09:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: T.create_cta }));

    expect(await screen.findByText(T.start_equals_end)).toBeInTheDocument();
    expect(screen.queryByText(T.midnight_span)).not.toBeInTheDocument();
    expect(screen.queryByText(T.start_after_end)).not.toBeInTheDocument();
  });

  test("time decision tree: start > end -> midnight_span (NOT start_after_end)", async () => {
    renderWithProviders(
      <ScheduleEditDialog open onOpenChange={() => {}} schedule={null} />,
    );
    await waitForPlaylistLoaded();

    fireEvent.change(getSelect(), {
      target: { value: "p1" },
    });
    fireEvent.click(getDayCheckbox("Mon"));
    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "22:00" },
    });
    fireEvent.change(screen.getByLabelText("End time"), {
      target: { value: "02:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: T.create_cta }));

    expect(await screen.findByText(T.midnight_span)).toBeInTheDocument();
    expect(screen.queryByText(T.start_after_end)).not.toBeInTheDocument();
  });

  test("time decision tree: malformed input -> time_format (short-circuits equal/reversal checks)", async () => {
    renderWithProviders(
      <ScheduleEditDialog open onOpenChange={() => {}} schedule={null} />,
    );
    await waitForPlaylistLoaded();

    fireEvent.change(getSelect(), {
      target: { value: "p1" },
    });
    fireEvent.click(getDayCheckbox("Mon"));
    // Leave start empty, end=09:00
    fireEvent.change(screen.getByLabelText("End time"), {
      target: { value: "09:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: T.create_cta }));

    expect(await screen.findByText(T.time_format)).toBeInTheDocument();
  });

  test("time decision tree: valid start < end -> no time error; createSchedule called with HHMM integers", async () => {
    renderWithProviders(
      <ScheduleEditDialog open onOpenChange={() => {}} schedule={null} />,
    );
    await waitForPlaylistLoaded();

    fireEvent.change(getSelect(), {
      target: { value: "p1" },
    });
    fireEvent.click(getDayCheckbox("Mon"));
    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "07:00" },
    });
    fireEvent.change(screen.getByLabelText("End time"), {
      target: { value: "11:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: T.create_cta }));

    await waitFor(() => {
      expect(signageApi.createSchedule).toHaveBeenCalledTimes(1);
    });
    expect(signageApi.createSchedule).toHaveBeenCalledWith(
      expect.objectContaining({
        playlist_id: "p1",
        start_hhmm: 700,
        end_hhmm: 1100,
        weekday_mask: 1,
      }),
    );
    expect(screen.queryByText(T.start_after_end)).not.toBeInTheDocument();
  });

  test("quick-pick Weekdays overwrites checkbox state (not union)", async () => {
    renderWithProviders(
      <ScheduleEditDialog open onOpenChange={() => {}} schedule={null} />,
    );
    await waitForPlaylistLoaded();

    // Manually check Saturday only
    fireEvent.click(getDayCheckbox("Sat"));
    expect(isChecked(getDayCheckbox("Sat"))).toBe(true);

    // Click Weekdays quick-pick -> overwrites to [Mo..Fr]
    fireEvent.click(screen.getByRole("button", { name: T.quickpick_weekdays }));

    expect(isChecked(getDayCheckbox("Mon"))).toBe(true);
    expect(isChecked(getDayCheckbox("Tue"))).toBe(true);
    expect(isChecked(getDayCheckbox("Wed"))).toBe(true);
    expect(isChecked(getDayCheckbox("Thu"))).toBe(true);
    expect(isChecked(getDayCheckbox("Fri"))).toBe(true);
    expect(isChecked(getDayCheckbox("Sat"))).toBe(false);
    expect(isChecked(getDayCheckbox("Sun"))).toBe(false);
  });

  test("quick-pick Daily overwrites to all 7; Weekend overwrites to Sa+So only", async () => {
    renderWithProviders(
      <ScheduleEditDialog open onOpenChange={() => {}} schedule={null} />,
    );
    await waitForPlaylistLoaded();

    fireEvent.click(screen.getByRole("button", { name: T.quickpick_daily }));
    for (const day of ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]) {
      expect(isChecked(getDayCheckbox(day))).toBe(true);
    }

    fireEvent.click(screen.getByRole("button", { name: T.quickpick_weekend }));
    for (const day of ["Mon", "Tue", "Wed", "Thu", "Fri"]) {
      expect(isChecked(getDayCheckbox(day))).toBe(false);
    }
    expect(isChecked(getDayCheckbox("Sat"))).toBe(true);
    expect(isChecked(getDayCheckbox("Sun"))).toBe(true);
  });

  test("renders friendly inline error when Directus rejects with schedule_end_before_start (Phase 68 MIG-SIGN-02 — create)", async () => {
    const err = new Error(JSON.stringify({ code: "schedule_end_before_start" }));
    vi.mocked(signageApi.createSchedule).mockRejectedValueOnce(err);
    const { toast } = await import("sonner");

    renderWithProviders(
      <ScheduleEditDialog open onOpenChange={() => {}} schedule={null} />,
    );
    await waitForPlaylistLoaded();

    fireEvent.change(getSelect(), { target: { value: "p1" } });
    fireEvent.click(getDayCheckbox("Mon"));
    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "07:00" },
    });
    fireEvent.change(screen.getByLabelText("End time"), {
      target: { value: "11:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: T.create_cta }));

    expect(await screen.findByText(T.start_after_end)).toBeInTheDocument();
    expect(toast.error).not.toHaveBeenCalled();
  });

  test("renders friendly inline error when Directus rejects with schedule_end_before_start (Phase 68 MIG-SIGN-02 — update via SDK error shape)", async () => {
    // Use the Directus SDK error shape: { errors: [{ extensions: { code } }] }
    const err = {
      errors: [{ message: "boom", extensions: { code: "schedule_end_before_start" } }],
    };
    vi.mocked(signageApi.updateSchedule).mockRejectedValueOnce(err);
    const { toast } = await import("sonner");

    const existing = {
      id: "s-1",
      playlist_id: "p1",
      weekday_mask: 1,
      start_hhmm: 700,
      end_hhmm: 1100,
      priority: 0,
      enabled: true,
      created_at: "x",
      updated_at: "x",
    };
    renderWithProviders(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      <ScheduleEditDialog open onOpenChange={() => {}} schedule={existing as any} />,
    );
    await waitForPlaylistLoaded();

    fireEvent.click(
      screen.getByRole("button", { name: "Save changes" }),
    );

    expect(await screen.findByText(T.start_after_end)).toBeInTheDocument();
    expect(toast.error).not.toHaveBeenCalled();
  });

  test("blur triggers per-field validation for touched fields (D-11)", async () => {
    renderWithProviders(
      <ScheduleEditDialog open onOpenChange={() => {}} schedule={null} />,
    );
    await waitForPlaylistLoaded();

    const playlist = getSelect();
    fireEvent.focus(playlist);
    fireEvent.blur(playlist);
    expect(await screen.findByText(T.playlist_required)).toBeInTheDocument();

    // Cross-field time revalidation on blur: start=07:00 end=06:00 -> midnight_span
    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "07:00" },
    });
    fireEvent.blur(screen.getByLabelText("Start time"));
    fireEvent.change(screen.getByLabelText("End time"), {
      target: { value: "06:00" },
    });
    fireEvent.blur(screen.getByLabelText("End time"));
    expect(await screen.findByText(T.midnight_span)).toBeInTheDocument();
  });
});
