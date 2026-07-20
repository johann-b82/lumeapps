import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { ClipboardCheck } from "lucide-react";

/**
 * Qualität hub (/quality/home). Landing page reached from the "Qualität"
 * launcher tile; groups the quality sub-features as tiles. Mirrors
 * ProductionHomePage.
 *
 * Phase 1 starts with the Audit-Modul (v1.84); more tiles dock here later. The
 * Qualitäts-KPI dashboard at /quality is deliberately NOT linked here — KPIs
 * live behind the KPI-Dashboard hub, same as Produktion keeps its Verzug KPI
 * out of the Produktion hub.
 */
export function QualityHomePage() {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
      <h1 className="text-lg font-semibold mb-6">{t("launcher.section.quality")}</h1>
      <div
        className="grid gap-8"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))" }}
      >
        {/* Audit-Modul tile → /quality/audit */}
        <div className="flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={() => setLocation("/quality/audit")}
            aria-label={t("audit.tile")}
            className="w-[120px] h-[120px] rounded-2xl
                       bg-gradient-to-br from-indigo-500 to-violet-700
                       shadow-md hover:shadow-xl hover:scale-[1.03]
                       flex items-center justify-center p-4
                       cursor-pointer transition-all
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ClipboardCheck className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
          </button>
          <span className="text-xs text-muted-foreground text-center">
            {t("audit.tile")}
          </span>
        </div>
      </div>
    </div>
  );
}
