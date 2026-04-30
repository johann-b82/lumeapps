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
  it("renders a single Select trigger (same control on desktop + mobile)", () => {
    renderFilter(vi.fn());
    const trigger = screen.getByTestId("date-range-filter-trigger");
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveAttribute("data-slot", "select-trigger");
  });

  it("trigger shows the translated label for the active preset (not the raw key)", () => {
    renderFilter(vi.fn());
    const trigger = screen.getByTestId("date-range-filter-trigger");
    // i18n at test time is "en" → "This Month"; assert that the raw key
    // "thisMonth" is NOT shown verbatim.
    expect(trigger.textContent ?? "").not.toContain("thisMonth");
    expect(trigger.textContent ?? "").toContain(i18n.t("dashboard.filter.thisMonth"));
  });

  it("trigger renders the German label after i18n.changeLanguage('de')", async () => {
    await i18n.changeLanguage("de");
    try {
      renderFilter(vi.fn());
      const trigger = screen.getByTestId("date-range-filter-trigger");
      // Regression guard for the screenshot the user filed: dropdown was
      // showing the raw key "thisMonth" instead of "Dieser Monat".
      expect(trigger.textContent ?? "").not.toContain("thisMonth");
      expect(trigger.textContent ?? "").toContain(i18n.t("dashboard.filter.thisMonth"));
    } finally {
      await i18n.changeLanguage("en");
    }
  });
});
