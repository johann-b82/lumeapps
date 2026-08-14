import { useState } from "react";
import { useTranslation } from "react-i18next";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { OtdCardGrid } from "@/components/dashboard/OtdCardGrid";
import { OtdChart } from "@/components/dashboard/OtdChart";
import { OtdTable } from "@/components/dashboard/OtdTable";
import { StockOrderTopTable } from "@/components/dashboard/StockOrderTopTable";
import { KpiBubbleOverlay } from "@/components/kpireview/KpiBubbleOverlay";

type ProcurementView = "otd" | "stock";

/**
 * Einkauf (procurement) dashboard with a top-level view toggle, mirroring
 * QualityPage:
 *   - Liefertermintreue / OTD  (OTD cards + chart + verification table)
 *   - Bestellung auf Lager     (Top-20 slow-mover ranking)
 */
export function ProcurementPage() {
  const { t } = useTranslation();
  const [view, setView] = useState<ProcurementView>("otd");

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8 space-y-8">
      <SegmentedControl<ProcurementView>
        segments={[
          { value: "otd", label: t("procurement.view.otd") },
          { value: "stock", label: t("procurement.view.stock") },
        ]}
        value={view}
        onChange={setView}
        aria-label={t("procurement.view.toggleLabel")}
      />

      {view === "otd" && (
        <>
          <OtdCardGrid />
          <KpiBubbleOverlay kpiKey="procurement.otd">
            <OtdChart />
          </KpiBubbleOverlay>
          <OtdTable />
        </>
      )}
      {view === "stock" && <StockOrderTopTable />}
    </div>
  );
}
