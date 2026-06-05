/**
 * BirthdaysCard — current ISO-week birthday roster for the HR landing.
 *
 * Reads from GET /api/hr/birthdays/this-week. Layout: a responsive grid of
 * one card per employee, sorted by the date of their birthday this week.
 * The card whose `occurs_on` matches today is highlighted with a "Today"
 * badge and a stronger border. Empty week shows a friendly empty state.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Cake } from "lucide-react";

import {
  fetchBirthdaysThisWeek,
  fetchBirthdaysThisWeekPublic,
  type BirthdayEntry,
} from "@/lib/api";
import { hrKpiKeys } from "@/lib/queryKeys";
import { Badge } from "@/components/ui/badge";

interface BirthdaysCardProps {
  /** Switch the data source + photo URL prefix to the unauthenticated mirror.
   *  Used by the /embed/birthdays signage page; the admin HR view leaves it
   *  off so behavior + photo provenance are unchanged. */
  embed?: boolean;
}

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

function initials(e: BirthdayEntry): string {
  const f = (e.first_name ?? "").trim()[0] ?? "";
  const l = (e.last_name ?? "").trim()[0] ?? "";
  const combined = (f + l).toUpperCase();
  return combined || "?";
}

/** Avatar component: Personio photo via proxy with an initials fallback.
 *  Uses a state flag rather than direct DOM manipulation so React can swap
 *  cleanly when the <img> 404s (Personio sometimes drops a photo between
 *  list-time and view-time). */
function Avatar({ entry, embed }: { entry: BirthdayEntry; embed: boolean }) {
  const [failed, setFailed] = useState(false);
  const showImage = entry.has_photo && !failed;
  const photoUrl = embed
    ? `/api/hr/embed/employees/${entry.employee_id}/photo`
    : `/api/hr/employees/${entry.employee_id}/photo`;
  return (
    <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-full bg-muted">
      {showImage ? (
        <img
          src={photoUrl}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        <span className="flex h-full w-full items-center justify-center text-sm font-semibold text-muted-foreground">
          {initials(entry)}
        </span>
      )}
    </div>
  );
}

function todayWeekdayIdx(): number {
  // Mirror Python's date.weekday() — Monday=0…Sunday=6 — so the highlight
  // lines up with the backend's `weekday` field even in en-US.
  const day = new Date().getDay();
  return day === 0 ? 6 : day - 1;
}

export function BirthdaysCard({ embed = false }: BirthdaysCardProps = {}) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const today = todayWeekdayIdx();

  const { data, isLoading, isError } = useQuery({
    queryKey: embed
      ? [...hrKpiKeys.birthdaysThisWeek(), "embed"]
      : hrKpiKeys.birthdaysThisWeek(),
    queryFn: embed ? fetchBirthdaysThisWeekPublic : fetchBirthdaysThisWeek,
    staleTime: 30 * 60_000, // a birthday doesn't move within the day
  });

  const formatDay = (iso: string) =>
    new Intl.DateTimeFormat(locale, { day: "numeric", month: "long" }).format(
      new Date(iso + "T00:00:00"),
    );

  return (
    <section className="rounded-xl bg-card p-6 text-card-foreground ring-1 ring-foreground/10">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Cake className="h-5 w-5 text-primary" aria-hidden="true" />
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
                  "flex items-start gap-3 rounded-xl bg-card p-4 ring-1 " +
                  (isToday
                    ? "ring-primary/40 bg-primary/5"
                    : "ring-foreground/10")
                }
              >
                <Avatar entry={entry} embed={embed} />
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
