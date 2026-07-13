import { useTranslation } from "react-i18next";
import { Network } from "lucide-react";

/**
 * HR › Organigramm. Placeholder — the org-chart view docks here later.
 */
export function OrganigrammPage() {
  const { t } = useTranslation();

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
        <Network className="h-12 w-12 text-muted-foreground" aria-hidden="true" />
        <h1 className="text-2xl font-semibold">{t("hr.organigramm.title")}</h1>
        <p className="text-muted-foreground">{t("hr.comingSoon")}</p>
      </div>
    </div>
  );
}
