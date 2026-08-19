import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { Bell } from "lucide-react";

import { useRole } from "@/auth/useAuth";
import { getFeedbackUnreadCount } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Top-right feedback bell (admin only) with an unread badge — the count of
 * feedback reports not yet viewed. Polls every 30s and refetches when the
 * window regains focus; the FeedbackPage invalidates ["feedback","unread"]
 * whenever a report is marked viewed so the badge updates immediately.
 */
export function FeedbackBell() {
  const { t } = useTranslation();
  const role = useRole();
  const [, navigate] = useLocation();

  const { data: count = 0 } = useQuery({
    queryKey: ["feedback", "unread"],
    queryFn: getFeedbackUnreadCount,
    enabled: role === "admin",
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  if (role !== "admin") return null;

  return (
    <button
      type="button"
      onClick={() => navigate("/feedback")}
      aria-label={t("feedback.bell.aria", { count })}
      className={cn(
        "relative inline-flex items-center justify-center rounded-full size-8 bg-muted text-foreground",
        "hover:bg-accent/20 transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      <Bell className="h-5 w-5" aria-hidden="true" />
      {count > 0 && (
        <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold leading-none text-white">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </button>
  );
}
