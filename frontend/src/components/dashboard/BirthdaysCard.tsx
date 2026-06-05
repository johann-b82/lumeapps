/**
 * BirthdaysCard — current ISO-week birthday roster for the HR landing.
 *
 * Reads from GET /api/hr/birthdays/this-week. Layout: today's birthdays sit
 * at the top in a slightly larger row with a 🎂 emoji and a "Today" pill;
 * the remaining six weekdays are listed below, grouped by weekday. Empty
 * weekdays are skipped. If the whole week is empty we show a friendly
 * "no birthdays this week" state.
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
  // Mirror Python's date.weekday() — Monday=0…Sunday=6 — so the badge picks
  // the right Today/Yesterday/etc row even if the user's locale is en-US.
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

  const grouped = new Map<number, BirthdayEntry[]>();
  for (const entry of data ?? []) {
    const bucket = grouped.get(entry.weekday) ?? [];
    bucket.push(entry);
    grouped.set(entry.weekday, bucket);
  }

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
        <ul className="divide-y divide-border">
          {WEEKDAY_KEYS.map((key, weekday) => {
            const rows = grouped.get(weekday) ?? [];
            if (rows.length === 0) return null;
            const isToday = weekday === today;
            return (
              <li key={key} className="py-3 first:pt-0 last:pb-0">
                <div className="mb-1 flex items-center gap-2">
                  <span
                    className={
                      isToday
                        ? "text-sm font-semibold text-foreground"
                        : "text-sm font-medium text-muted-foreground"
                    }
                  >
                    {t(key)} · {formatDay(rows[0].occurs_on)}
                  </span>
                  {isToday && (
                    <Badge variant="secondary" className="text-xs">
                      {t("hr.birthdays.today")}
                    </Badge>
                  )}
                </div>
                <ul className="space-y-1">
                  {rows.map((entry) => (
                    <li
                      key={entry.employee_id}
                      className="flex items-baseline gap-3 text-sm"
                    >
                      <span className="font-medium">
                        {displayName(entry)}
                        {entry.department && (
                          <span className="ml-2 text-xs text-muted-foreground">
                            {entry.department}
                          </span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
