import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { ListChecks } from "lucide-react";

import { useRole } from "@/auth/useAuth";
import { fetchKpiMeasures } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Top-right nav entry (admin only) to the dedicated measures page, with a badge
 * counting still-open measures (open + in_progress) across all KPIs — the
 * management counterpart to the feedback bell.
 */
export function MeasuresNavLink() {
  const { t } = useTranslation();
  const role = useRole();
  const [, navigate] = useLocation();

  const { data: count = 0 } = useQuery({
    queryKey: ["kpi-review", "measures-nav"],
    queryFn: () => fetchKpiMeasures({}),
    enabled: role === "admin",
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
    select: (rows) =>
      rows.filter((m) => m.status === "open" || m.status === "in_progress").length,
  });

  if (role !== "admin") return null;

  return (
    <button
      type="button"
      onClick={() => navigate("/kpi-review")}
      aria-label={t("kpireview.measures.navAria", { count })}
      className={cn(
        "relative inline-flex items-center justify-center rounded-full size-8 bg-muted text-foreground",
        "hover:bg-accent/20 transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      <ListChecks className="h-5 w-5" aria-hidden="true" />
      {count > 0 && (
        <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold leading-none text-white">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </button>
  );
}
