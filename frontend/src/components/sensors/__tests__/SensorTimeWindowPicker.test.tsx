import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n";
import {
  SensorTimeWindowPicker,
  SensorTimeWindowProvider,
} from "@/components/sensors/SensorTimeWindow";

function renderPicker() {
  return render(
    <I18nextProvider i18n={i18n}>
      <SensorTimeWindowProvider>
        <SensorTimeWindowPicker />
      </SensorTimeWindowProvider>
    </I18nextProvider>,
  );
}

describe("SensorTimeWindowPicker", () => {
  it("renders a single Select trigger (same control on desktop + mobile)", () => {
    renderPicker();
    expect(screen.getByTestId("sensor-time-window-trigger")).toBeInTheDocument();
  });

  it("trigger shows the translated label for the default '24h' window (not the raw key)", () => {
    renderPicker();
    const trigger = screen.getByTestId("sensor-time-window-trigger");
    expect(trigger.textContent ?? "").toContain(i18n.t("sensors.window.24h"));
  });

  it("trigger renders the German label after i18n.changeLanguage('de')", async () => {
    await i18n.changeLanguage("de");
    try {
      renderPicker();
      const trigger = screen.getByTestId("sensor-time-window-trigger");
      // Regression guard alongside the dashboard DateRangeFilter case:
      // dropdown was showing the raw key (e.g. "24h") instead of the
      // translated label.
      expect(trigger.textContent ?? "").toContain(i18n.t("sensors.window.24h"));
    } finally {
      await i18n.changeLanguage("en");
    }
  });
});
