import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { MessageSquareDashed } from "lucide-react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useRole } from "@/auth/useAuth";
import { getUnreadBubbles } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Top-right bubble bell (admin only) with a badge counting bubbles not yet
 * viewed. Clicking opens a list of the new bubbles; each links to its KPI
 * dashboard (the bubble's kpi_key is the dashboard route). A bubble is marked
 * viewed when the admin clicks it on the chart (KpiBubbleOverlay), which
 * invalidates ["kpi-review","bubbles-unread"] so the badge updates.
 */
export function BubbleBell() {
  const { t } = useTranslation();
  const role = useRole();
  const [, navigate] = useLocation();
  const [open, setOpen] = useState(false);

  const { data = [] } = useQuery({
    queryKey: ["kpi-review", "bubbles-unread"],
    queryFn: getUnreadBubbles,
    enabled: role === "admin",
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  if (role !== "admin") return null;
  const count = data.length;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        aria-label={t("kpireview.bubble.bellAria", { count })}
        className={cn(
          "relative inline-flex items-center justify-center rounded-full size-8 bg-muted text-foreground",
          "hover:bg-accent/20 transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <MessageSquareDashed className="h-5 w-5" aria-hidden="true" />
        {count > 0 && (
          <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold leading-none text-white">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 gap-0 p-0">
        <p className="border-b border-border px-3 py-2 text-sm font-semibold">
          {t("kpireview.bubble.bellTitle")}{" "}
          <span className="font-normal text-muted-foreground">({count})</span>
        </p>
        {count === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground">
            {t("kpireview.bubble.bellEmpty")}
          </p>
        ) : (
          <ul className="max-h-80 overflow-y-auto py-1">
            {data.map((b) => (
              <li key={b.id}>
                <button
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    navigate(`/${b.kpi_key}`);
                  }}
                  className="flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-muted/50"
                >
                  <span
                    className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-white"
                    aria-hidden
                  >
                    {b.number ?? "•"}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-xs font-medium text-muted-foreground">
                      {t(`kpireview.domain.${b.kpi_key}`)}
                    </span>
                    <span className="block truncate text-sm">{b.body}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}
