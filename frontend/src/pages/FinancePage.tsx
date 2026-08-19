import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Toggle } from "@/components/ui/toggle";
import { MaterialCostRatioCardGrid } from "@/components/dashboard/MaterialCostRatioCardGrid";
import { MaterialCostRatioChart } from "@/components/dashboard/MaterialCostRatioChart";
import { MaterialCostRatioTable } from "@/components/dashboard/MaterialCostRatioTable";
import { PersonnelCostRatioCardGrid } from "@/components/dashboard/PersonnelCostRatioCardGrid";
import { PersonnelCostRatioChart } from "@/components/dashboard/PersonnelCostRatioChart";
import { PersonnelCostRatioTable } from "@/components/dashboard/PersonnelCostRatioTable";
import { KpiBubbleOverlay } from "@/components/kpireview/KpiBubbleOverlay";

type FinanceView = "material" | "personnel";

/**
 * Finanzperspektive (finance) dashboard. Top-level view toggle — Material |
 * Personal — mirroring QualityPage's Audits | Reklamationen. Each view shows
 * its own cards + chart + verification table over the shared date range.
 * Umsatzrendite docks on as a third segment later.
 */
export function FinancePage() {
  const { t } = useTranslation();
  const [view, setView] = useState<FinanceView>("material");

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
      <KpiBubbleOverlay kpiKey="finance">
        <div className="space-y-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <Toggle<FinanceView>
              segments={[
                { value: "material", label: t("finance.view.material") },
                { value: "personnel", label: t("finance.view.personnel") },
              ] as const}
              value={view}
              onChange={setView}
              aria-label={t("finance.view.toggleLabel")}
              variant="muted"
            />
          </div>

          {view === "material" ? (
            <>
              <MaterialCostRatioCardGrid />
              <MaterialCostRatioChart />
              <MaterialCostRatioTable />
            </>
          ) : (
            <>
              <PersonnelCostRatioCardGrid />
              <PersonnelCostRatioChart />
              <PersonnelCostRatioTable />
            </>
          )}
        </div>
      </KpiBubbleOverlay>
    </div>
  );
}
