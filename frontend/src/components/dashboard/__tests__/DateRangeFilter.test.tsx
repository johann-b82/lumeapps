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
