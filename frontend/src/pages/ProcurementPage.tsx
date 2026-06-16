import { useTranslation } from "react-i18next";
import { OtdCardGrid } from "@/components/dashboard/OtdCardGrid";
import { OtdChart } from "@/components/dashboard/OtdChart";
import { OtdTable } from "@/components/dashboard/OtdTable";

/**
 * Einkauf (procurement) dashboard. First section: Liefertermintreue / OTD.
 *
 * The two planned sections (On Quality – Werkbänke, On Quality – Material
 * Lieferanten) will dock on here as a top-level view toggle, mirroring how
 * QualityPage split into Audits / Reklamationen.
 */
export function ProcurementPage() {
  const { t } = useTranslation();

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8 space-y-8">
      <h2 className="text-lg font-semibold">
        {t("procurement.otd.sectionTitle")}
      </h2>
      <OtdCardGrid />
      <OtdChart />
      <OtdTable />
    </div>
  );
}
