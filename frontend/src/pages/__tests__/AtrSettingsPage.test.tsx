// frontend/src/pages/__tests__/AtrSettingsPage.test.tsx
import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import { describe, it, expect, vi, beforeEach } from "vitest";
import i18n from "@/i18n";
import { AtrSettingsPage } from "../AtrSettingsPage";
import * as api from "@/lib/api";

vi.mock("@/lib/api");

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}><I18nextProvider i18n={i18n}>{ui}</I18nextProvider></QueryClientProvider>;
}

describe("AtrSettingsPage", () => {
  beforeEach(() => vi.resetAllMocks());
  it("renders fileserver fields from settings", async () => {
    vi.mocked(api.fetchSettings).mockResolvedValue({
      color_primary: "x", color_accent: "x", color_background: "x", color_foreground: "x",
      color_muted: "x", color_destructive: "x", app_name: "A", logo_url: null, logo_updated_at: null,
      personio_has_credentials: false, personio_sync_interval_h: 168, personio_sick_leave_type_id: [],
      personio_production_dept: [], personio_skill_attr_key: [], target_overtime_ratio: null,
      target_sick_leave_ratio: null, target_fluctuation: null, target_revenue_per_employee: null,
      target_sales_erstkontakte: null, target_sales_interessenten: null, target_sales_besuche: null,
      target_sales_angebote_eur: null, target_sales_orders_per_rep_eur: null,
      sensor_poll_interval_s: 60, sensor_temperature_min: null, sensor_temperature_max: null,
      sensor_humidity_min: null, sensor_humidity_max: null, worldcup_has_api_key: false,
      worldcup_refresh_seconds: 60,
      atr_smb_host: "acm_file", atr_smb_share: "Dateiablage", atr_smb_domain: "ACME",
      atr_smb_user: "svc", atr_smb_has_password: true, atr_input_path: "0900 - EDV/Test_ATR/Input",
      atr_output_path: "0900 - EDV/Test_ATR/Output", atr_archive_path: "0900 - EDV/Test_ATR/Archiv",
      atr_scan_interval_s: 0, atr_auto_mode: false,
    } as unknown as api.Settings);
    render(wrap(<AtrSettingsPage />));
    await waitFor(() => expect(screen.getByDisplayValue("acm_file")).toBeInTheDocument());
    expect(screen.getByDisplayValue("Dateiablage")).toBeInTheDocument();
  });
});
