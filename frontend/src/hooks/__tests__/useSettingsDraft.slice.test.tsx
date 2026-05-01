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
