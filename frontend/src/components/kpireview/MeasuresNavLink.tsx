import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { ListChecks } from "lucide-react";

import { useRole } from "@/auth/useAuth";
import { getUnreadBubbles } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Top-right nav entry (admin only) to the KPI-Bewertung & Maßnahmen page. The
 * badge counts still-unviewed bubbles across all KPIs — new bubbles surface
 * here (the standalone bubble bell was folded into this entry). A bubble is
 * marked viewed when opened on a chart or in the page's bubble list, which
 * invalidates ["kpi-review","bubbles-unread"] so the badge updates.
 */
export function MeasuresNavLink() {
  const { t } = useTranslation();
  const role = useRole();
  const [, navigate] = useLocation();

  const { data: count = 0 } = useQuery({
    queryKey: ["kpi-review", "bubbles-unread"],
    queryFn: getUnreadBubbles,
    enabled: role === "admin",
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    select: (rows) => rows.length,
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
        <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold leading-none text-white">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </button>
  );
}
