import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { UserPlus, Network, GraduationCap, Award } from "lucide-react";
import { AdminOnly } from "@/auth/AdminOnly";

/**
 * HR hub (/hr/home). Landing page reached from the single "HR" launcher tile;
 * groups the HR sub-features (Onboarding, Schulungen, Kompetenzen, Organigramm)
 * as tiles. More tiles dock here later. The /hr KPI dashboard is a separate
 * route reached from the KPI-Dashboard hub.
 */
export function HrHomePage() {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
      <h1 className="text-lg font-semibold mb-6">{t("launcher.section.hr")}</h1>
      <div
        className="grid gap-8"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))" }}
      >
        {/* Onboarding tile → /hr/onboarding */}
        <div className="flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={() => setLocation("/hr/onboarding")}
            aria-label={t("launcher.tile.onboarding")}
            className="w-[120px] h-[120px] rounded-2xl
                       bg-gradient-to-br from-fuchsia-500 to-purple-600
                       shadow-md hover:shadow-xl hover:scale-[1.03]
                       flex items-center justify-center p-4
                       cursor-pointer transition-all
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <UserPlus className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
          </button>
          <span className="text-xs text-muted-foreground text-center">
            {t("launcher.tile.onboarding")}
          </span>
        </div>

        {/* Schulungen tile → /hr/schulungen (admin-only, wie der Backend-Router) */}
        <AdminOnly>
          <div className="flex flex-col items-center gap-2">
            <button
              type="button"
              onClick={() => setLocation("/hr/schulungen")}
              aria-label={t("schulungen.title")}
              className="w-[120px] h-[120px] rounded-2xl
                         bg-gradient-to-br from-amber-500 to-orange-600
                         shadow-md hover:shadow-xl hover:scale-[1.03]
                         flex items-center justify-center p-4
                         cursor-pointer transition-all
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <GraduationCap className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
            </button>
            <span className="text-xs text-muted-foreground text-center">
              {t("schulungen.title")}
            </span>
          </div>
        </AdminOnly>

        {/* Kompetenzen tile → /hr/kompetenzen (admin-only wie Schulungen) */}
        <AdminOnly>
          <div className="flex flex-col items-center gap-2">
            <button
              type="button"
              onClick={() => setLocation("/hr/kompetenzen")}
              aria-label={t("kompetenzen.title")}
              className="w-[120px] h-[120px] rounded-2xl
                         bg-gradient-to-br from-emerald-500 to-teal-700
                         shadow-md hover:shadow-xl hover:scale-[1.03]
                         flex items-center justify-center p-4
                         cursor-pointer transition-all
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Award className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
            </button>
            <span className="text-xs text-muted-foreground text-center">
              {t("kompetenzen.title")}
            </span>
          </div>
        </AdminOnly>

        {/* Organigramm tile → /hr/organigramm */}
        <div className="flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={() => setLocation("/hr/organigramm")}
            aria-label={t("launcher.tile.organigramm")}
            className="w-[120px] h-[120px] rounded-2xl
                       bg-gradient-to-br from-cyan-500 to-sky-700
                       shadow-md hover:shadow-xl hover:scale-[1.03]
                       flex items-center justify-center p-4
                       cursor-pointer transition-all
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Network className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
          </button>
          <span className="text-xs text-muted-foreground text-center">
            {t("launcher.tile.organigramm")}
          </span>
        </div>
      </div>
    </div>
  );
}
