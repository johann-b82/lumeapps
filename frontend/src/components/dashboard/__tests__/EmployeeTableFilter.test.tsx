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

describe("EmployeeTable filter", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("[]", { status: 200 }),
    );
  });

  it("renders a single Select trigger (same control on desktop + mobile)", () => {
    renderTable();
    expect(screen.getByTestId("employee-filter-trigger")).toBeInTheDocument();
  });

  it("trigger shows the translated label for the active filter (not the raw key)", () => {
    renderTable();
    const trigger = screen.getByTestId("employee-filter-trigger");
    // Default filter is "overtime" — assert the raw value isn't shown
    // verbatim and the translated label is.
    expect(trigger.textContent ?? "").not.toBe("overtime");
    expect(trigger.textContent ?? "").toContain(i18n.t("hr.table.showOvertime"));
  });
});
