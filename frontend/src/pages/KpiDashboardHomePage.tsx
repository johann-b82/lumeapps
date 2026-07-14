/**
 * KpiDashboardHomePage — the hub the top-level "KPI-Dashboard" launcher
 * tile drops into (v1.82).
 *
 * Renders one tile per KPI section — Vertrieb, Einkauf, Produktion, HR,
 * Qualität, Finanzperspektive — reusing the same visual language as the
 * outer LauncherPage: 120 × 120 rounded card, coloured gradient, white
 * lucide icon, i18n label below. Clicking a tile routes to its section's
 * existing URL (``/sales``, ``/procurement``, …); switching sections
 * mid-flow is still handled by the ``SubHeader`` section-picker.
 *
 * Kept as a standalone page instead of an embed-in-DashboardPage so the
 * chrome (SubHeader dashboard-select, DateRangeFilter, upload icon) can
 * stay hidden on the hub and only appears once the user is inside a
 * specific section.
 */
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import {
  LayoutDashboard,
  ShoppingCart,
  Factory,
  Users,
  ShieldCheck,
  Coins,
  type LucideIcon,
} from "lucide-react";

interface Tile {
  path: string;
  labelKey: string;
  icon: LucideIcon;
  gradient: string;
}

// Order per customer request 2026-07-13: Vertrieb → Einkauf → Produktion
// → HR → Qualität → Finanzperspektive. Colours + icons reuse the values
// the section tiles carried on the outer launcher so returning users
// keep the same colour-to-section muscle memory.
const TILES: readonly Tile[] = [
  {
    path: "/sales",
    labelKey: "nav.sales",
    icon: LayoutDashboard,
    gradient: "from-blue-500 to-indigo-600",
  },
  {
    path: "/procurement",
    labelKey: "nav.procurement",
    icon: ShoppingCart,
    gradient: "from-amber-400 to-orange-600",
  },
  {
    path: "/production",
    labelKey: "nav.production",
    icon: Factory,
    gradient: "from-sky-500 to-blue-700",
  },
  {
    path: "/hr",
    labelKey: "nav.hr",
    icon: Users,
    gradient: "from-pink-400 to-rose-600",
  },
  {
    path: "/quality",
    labelKey: "nav.quality",
    icon: ShieldCheck,
    gradient: "from-emerald-400 to-cyan-600",
  },
  {
    path: "/finance",
    labelKey: "nav.finance",
    icon: Coins,
    gradient: "from-lime-500 to-green-600",
  },
];

export function KpiDashboardHomePage() {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();

  return (
    <div className="max-w-7xl mx-auto px-6 pt-16 pb-8">
      <div
        className="grid gap-8"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))" }}
      >
        {TILES.map(({ path, labelKey, icon: Icon, gradient }) => (
          <div key={path} className="flex flex-col items-center gap-2">
            <button
              type="button"
              onClick={() => setLocation(path)}
              aria-label={t(labelKey)}
              className={`w-[120px] h-[120px] rounded-2xl
                         bg-gradient-to-br ${gradient}
                         shadow-md hover:shadow-xl hover:scale-[1.03]
                         flex items-center justify-center p-4
                         cursor-pointer transition-all
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring`}
            >
              <Icon
                className="w-12 h-12 text-white drop-shadow"
                aria-hidden="true"
              />
            </button>
            <span className="text-xs text-muted-foreground text-center">
              {t(labelKey)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
