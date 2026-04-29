import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { LayoutDashboard, Box, Thermometer, MonitorPlay } from "lucide-react";
import { useAuth } from "@/auth/useAuth";
import { AdminOnly } from "@/auth/AdminOnly";

export function LauncherPage() {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();
  const { user } = useAuth();

  // LAUNCH-05 / D-05: Admin-only tiles absent (not greyed) for viewer role.
  // v1.15 SEN-LNCH-01: Sensors tile is admin-only; viewer sees no slot at all.
  // Using <AdminOnly> child gating — hook stays for future role-specific logic.
  void user;

  return (
    <div className="max-w-7xl mx-auto px-8 pt-16 pb-8">
      <div
        className="grid gap-8"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))" }}
      >
        {/* Active tile: KPI Dashboard → navigates to /sales (Sales Dashboard route) */}
        <div className="flex flex-col items-center gap-2">
          {/* CTRL-02 exception: launcher tile — card-surface click target, Button's fixed chrome does not fit the grid-tile visual. */}
          <button
            type="button"
            onClick={() => setLocation("/sales")}
            aria-label={t("launcher.tile.kpi_dashboard")}
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
            {t("launcher.tile.kpi_dashboard")}
          </span>
        </div>

        {/* v1.15 SEN-LNCH: Sensors tile (admin-only, replaces first coming-soon slot) */}
        <AdminOnly>
          <div className="flex flex-col items-center gap-2">
            {/* CTRL-02 exception: launcher tile — card-surface click target, Button's fixed chrome does not fit the grid-tile visual. */}
            <button
              type="button"
              onClick={() => setLocation("/sensors")}
              aria-label={t("launcher.tile.sensors")}
              className="w-[120px] h-[120px] rounded-2xl
                         bg-gradient-to-br from-orange-400 to-red-500
                         shadow-md hover:shadow-xl hover:scale-[1.03]
                         flex items-center justify-center p-4
                         cursor-pointer transition-all
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Thermometer className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
            </button>
            <span className="text-xs text-muted-foreground text-center">
              {t("launcher.tile.sensors")}
            </span>
          </div>
        </AdminOnly>

        {/* Phase 46 SGN-ADM-02: Digital Signage tile (admin-only, replaces second coming-soon slot) */}
        <AdminOnly>
          <div className="flex flex-col items-center gap-2">
            {/* CTRL-02 exception: launcher tile — card-surface click target, Button's fixed chrome does not fit the grid-tile visual. */}
            <button
              type="button"
              onClick={() => setLocation("/signage")}
              aria-label={t("launcher.tiles.signage")}
              className="w-[120px] h-[120px] rounded-2xl
                         bg-gradient-to-br from-violet-500 to-fuchsia-600
                         shadow-md hover:shadow-xl hover:scale-[1.03]
                         flex items-center justify-center p-4
                         cursor-pointer transition-all
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <MonitorPlay className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
            </button>
            <span className="text-xs text-muted-foreground text-center">
              {t("launcher.tiles.signage")}
            </span>
          </div>
        </AdminOnly>

        {/* Coming-soon tiles (1x) — opacity-40 + pointer-events-none per D-04 */}
        {[0].map((i) => (
          <div key={`coming-soon-${i}`} className="flex flex-col items-center gap-2">
            <div
              aria-hidden="true"
              className="w-[120px] h-[120px] rounded-2xl
                         bg-gradient-to-br from-neutral-300 to-neutral-400
                         shadow-md
                         flex items-center justify-center p-4
                         opacity-60 pointer-events-none"
            >
              <Box className="w-12 h-12 text-white drop-shadow" />
            </div>
            <span className="text-xs text-muted-foreground text-center opacity-40">
              {t("launcher.tile.coming_soon")}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
