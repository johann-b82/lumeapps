import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { Wrench } from "lucide-react";

/**
 * Produktion hub (/production/home). Landing page reached from the "Produktion"
 * launcher tile; groups the production sub-features as tiles. Phase 1 starts
 * with Wartung (machine maintenance); more tiles dock here later. The Verzug
 * KPI stays a separate route reached from the KPI-Dashboard hub.
 */
export function ProductionHomePage() {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
      <h1 className="text-lg font-semibold mb-6">
        {t("launcher.section.production")}
      </h1>
      <div
        className="grid gap-8"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))" }}
      >
        {/* Wartung tile → /production/maintenance */}
        <div className="flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={() => setLocation("/production/maintenance")}
            aria-label={t("maintenance.tile")}
            className="w-[120px] h-[120px] rounded-2xl
                       bg-gradient-to-br from-sky-500 to-blue-700
                       shadow-md hover:shadow-xl hover:scale-[1.03]
                       flex items-center justify-center p-4
                       cursor-pointer transition-all
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Wrench className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
          </button>
          <span className="text-xs text-muted-foreground text-center">
            {t("maintenance.tile")}
          </span>
        </div>
      </div>
    </div>
  );
}
