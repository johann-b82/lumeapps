/**
 * BirthdaysCard — current ISO-week birthday roster for the HR landing.
 *
 * Reads from GET /api/hr/birthdays/this-week. Layout: a responsive grid of
 * one card per employee, sorted by the date of their birthday this week.
 * The card whose `occurs_on` matches today is highlighted with a "Today"
 * badge and a stronger border. Empty week shows a friendly empty state.
 */
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Cake } from "lucide-react";

import { fetchBirthdaysThisWeek, type BirthdayEntry } from "@/lib/api";
import { hrKpiKeys } from "@/lib/queryKeys";
import { Badge } from "@/components/ui/badge";

const WEEKDAY_KEYS = [
  "common.weekday.monday",
  "common.weekday.tuesday",
  "common.weekday.wednesday",
  "common.weekday.thursday",
  "common.weekday.friday",
  "common.weekday.saturday",
  "common.weekday.sunday",
] as const;

function displayName(e: BirthdayEntry): string {
  const parts = [e.first_name, e.last_name].filter((p): p is string => !!p);
  return parts.length ? parts.join(" ") : `#${e.employee_id}`;
}

function todayWeekdayIdx(): number {
  // Mirror Python's date.weekday() — Monday=0…Sunday=6 — so the highlight
  // lines up with the backend's `weekday` field even in en-US.
  const day = new Date().getDay();
  return day === 0 ? 6 : day - 1;
}

export function BirthdaysCard() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const today = todayWeekdayIdx();

  const { data, isLoading, isError } = useQuery({
    queryKey: hrKpiKeys.birthdaysThisWeek(),
    queryFn: fetchBirthdaysThisWeek,
    staleTime: 30 * 60_000, // a birthday doesn't move within the day
  });

  const formatDay = (iso: string) =>
    new Intl.DateTimeFormat(locale, { day: "numeric", month: "long" }).format(
      new Date(iso + "T00:00:00"),
    );

  return (
    <section className="rounded-lg border border-border bg-card p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Cake className="h-5 w-5 text-pink-500" aria-hidden="true" />
          {t("hr.birthdays.title")}
        </h2>
      </div>

      {isLoading && (
        <p className="text-sm text-muted-foreground">
          {t("common.loading")}
        </p>
      )}

      {isError && (
        <p className="text-sm text-destructive">
          {t("hr.birthdays.error")}
        </p>
      )}

      {!isLoading && !isError && (data?.length ?? 0) === 0 && (
        <p className="text-sm text-muted-foreground">
          {t("hr.birthdays.empty")}
        </p>
      )}

      {!isLoading && !isError && (data?.length ?? 0) > 0 && (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {(data ?? []).map((entry) => {
            const isToday = entry.weekday === today;
            return (
              <li
                key={entry.employee_id}
                className={
                  "flex items-start gap-3 rounded-lg border p-4 " +
                  (isToday
                    ? "border-pink-400/70 bg-pink-50/50 dark:bg-pink-950/20"
                    : "border-border bg-background")
                }
              >
                <Cake
                  className={
                    "h-7 w-7 shrink-0 " +
                    (isToday ? "text-pink-500" : "text-muted-foreground/70")
                  }
                  aria-hidden="true"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold">
                      {displayName(entry)}
                    </span>
                    {isToday && (
                      <Badge variant="secondary" className="text-xs">
                        {t("hr.birthdays.today")}
                      </Badge>
                    )}
                  </div>
                  {entry.department && (
                    <p className="truncate text-xs text-muted-foreground">
                      {entry.department}
                    </p>
                  )}
                  <p className="mt-1 text-xs text-muted-foreground tabular-nums">
                    {t(WEEKDAY_KEYS[entry.weekday])} · {formatDay(entry.occurs_on)}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
