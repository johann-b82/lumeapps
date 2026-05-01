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
    role: "admin",
    isLoading: false,
    signIn: vi.fn(),
    signOut: vi.fn(),
  }),
  useRole: () => "admin",
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
    expect(await screen.findByLabelText(/app name|app-name/i)).toBeInTheDocument();
  });
});
