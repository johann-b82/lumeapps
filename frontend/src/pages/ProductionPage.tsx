import { useTranslation } from "react-i18next";
import { ProductionVerzugCardGrid } from "@/components/dashboard/ProductionVerzugCardGrid";
import { ProductionVerzugChart } from "@/components/dashboard/ProductionVerzugChart";
import { ProductionVerzugTable } from "@/components/dashboard/ProductionVerzugTable";

/**
 * Produktion dashboard. First section: Aufträge in Verzug (Seriengeschäft).
 *
 * The planned second section ("Aufträge mit Verzugsgefahr") will dock on here
 * as a top-level view toggle, mirroring how QualityPage split into
 * Audits / Reklamationen.
 */
export function ProductionPage() {
  const { t } = useTranslation();

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8 space-y-8">
      <h2 className="text-lg font-semibold">
        {t("production.verzug.sectionTitle")}
      </h2>
      <ProductionVerzugCardGrid />
      <ProductionVerzugChart />
      <ProductionVerzugTable />
    </div>
  );
}
