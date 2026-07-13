import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { LayoutDashboard, ShoppingCart, Factory, Users, ShieldCheck, Coins } from "lucide-react";

/**
 * KPI-Dashboard hub (/kpi). Landing page reached from the single
 * "KPI-Dashboard" launcher tile; groups the six business KPI dashboards
 * (Vertrieb, Einkauf, Produktion, HR, Qualität, Finanzperspektive) as tiles.
 */
export function KpiDashboardHomePage() {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
      <h1 className="text-lg font-semibold mb-6">{t("launcher.section.kpi")}</h1>
      <div
        className="grid gap-8"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))" }}
      >
        {/* Vertrieb (Sales dashboard) → /sales */}
        <div className="flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={() => setLocation("/sales")}
            aria-label={t("launcher.tile.sales")}
            className="w-[120px] h-[120px] rounded-2xl
                       bg-gradient-to-br from-blue-500 to-indigo-600
                       shadow-md hover:shadow-xl hover:scale-[1.03]
                       flex items-center justify-center p-4
                       cursor-pointer transition-all
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <LayoutDashboard className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
          </button>
          <span className="text-xs text-muted-foreground text-center">
            {t("launcher.tile.sales")}
          </span>
        </div>

        {/* Einkauf (procurement) → /procurement */}
        <div className="flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={() => setLocation("/procurement")}
            aria-label={t("launcher.tile.procurement")}
            className="w-[120px] h-[120px] rounded-2xl
                       bg-gradient-to-br from-amber-400 to-orange-600
                       shadow-md hover:shadow-xl hover:scale-[1.03]
                       flex items-center justify-center p-4
                       cursor-pointer transition-all
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ShoppingCart className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
          </button>
          <span className="text-xs text-muted-foreground text-center">
            {t("launcher.tile.procurement")}
          </span>
        </div>

        {/* Produktion → /production */}
        <div className="flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={() => setLocation("/production")}
            aria-label={t("launcher.tile.production")}
            className="w-[120px] h-[120px] rounded-2xl
                       bg-gradient-to-br from-sky-500 to-blue-700
                       shadow-md hover:shadow-xl hover:scale-[1.03]
                       flex items-center justify-center p-4
                       cursor-pointer transition-all
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Factory className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
          </button>
          <span className="text-xs text-muted-foreground text-center">
            {t("launcher.tile.production")}
          </span>
        </div>

        {/* HR → /hr */}
        <div className="flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={() => setLocation("/hr")}
            aria-label={t("launcher.tile.hr")}
            className="w-[120px] h-[120px] rounded-2xl
                       bg-gradient-to-br from-pink-400 to-rose-600
                       shadow-md hover:shadow-xl hover:scale-[1.03]
                       flex items-center justify-center p-4
                       cursor-pointer transition-all
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Users className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
          </button>
          <span className="text-xs text-muted-foreground text-center">
            {t("launcher.tile.hr")}
          </span>
        </div>

        {/* Qualität → /quality */}
        <div className="flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={() => setLocation("/quality")}
            aria-label={t("launcher.tile.quality")}
            className="w-[120px] h-[120px] rounded-2xl
                       bg-gradient-to-br from-emerald-400 to-cyan-600
                       shadow-md hover:shadow-xl hover:scale-[1.03]
                       flex items-center justify-center p-4
                       cursor-pointer transition-all
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ShieldCheck className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
          </button>
          <span className="text-xs text-muted-foreground text-center">
            {t("launcher.tile.quality")}
          </span>
        </div>

        {/* Finanzperspektive → /finance */}
        <div className="flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={() => setLocation("/finance")}
            aria-label={t("launcher.tile.finance")}
            className="w-[120px] h-[120px] rounded-2xl
                       bg-gradient-to-br from-lime-500 to-green-600
                       shadow-md hover:shadow-xl hover:scale-[1.03]
                       flex items-center justify-center p-4
                       cursor-pointer transition-all
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Coins className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
          </button>
          <span className="text-xs text-muted-foreground text-center">
            {t("launcher.tile.finance")}
          </span>
        </div>
      </div>
    </div>
  );
}
