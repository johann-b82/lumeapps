import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { KPI_INFO_KEYS, getKpiInfo } from "@/lib/kpiInfo";

function renderCard(withInfo: boolean) {
  return render(
    <I18nextProvider i18n={i18n}>
      <KpiCard
        label="Umsatz"
        value="1.000 €"
        isLoading={false}
        infoKey={withInfo ? "sales.revenue" : undefined}
      />
    </I18nextProvider>,
  );
}

describe("KpiInfoButton", () => {
  it("renders no button when the card has no infoKey", () => {
    renderCard(false);
    expect(screen.queryByTestId("kpi-info-sales.revenue")).toBeNull();
  });

  it("opens a dialog with the calculation notes for the KPI", () => {
    renderCard(true);
    const btn = screen.getByTestId("kpi-info-sales.revenue");
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    // Dialog title carries the KPI label; body contains the formula heading.
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/Umsatz/, { selector: "h2" })).toBeInTheDocument();
    expect(screen.getByText(/SUM\(wert_eur\)/)).toBeInTheDocument();
  });
});

describe("kpiInfo content", () => {
  it("has a German and an English body for every key", () => {
    for (const key of KPI_INFO_KEYS) {
      const de = getKpiInfo(key, "de");
      const en = getKpiInfo(key, "en");
      expect(de.length, `${key} de`).toBeGreaterThan(40);
      expect(en.length, `${key} en`).toBeGreaterThan(40);
      expect(de, `${key} de differs from en`).not.toBe(en);
      // Footer names the source file and the backend code location.
      expect(de, `${key} footer de`).toMatch(/\*\*Quelldatei:\*\* .+/);
      expect(en, `${key} footer en`).toMatch(/\*\*Source file:\*\* .+/);
      expect(de, `${key} code`).toMatch(/\*\*Code:\*\* `backend\//);
    }
  });

  it("appends the shared period paragraph only for range-based KPIs", () => {
    expect(getKpiInfo("sales.revenue", "de")).toContain("Zeitraum & Vergleich");
    expect(getKpiInfo("hr.weekly_saldo", "de")).not.toContain("Zeitraum & Vergleich");
    expect(getKpiInfo("procurement.stock_orders", "en")).not.toContain("Period & comparison");
  });
});
