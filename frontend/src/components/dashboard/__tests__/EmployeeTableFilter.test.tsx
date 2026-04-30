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
