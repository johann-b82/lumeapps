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
  // Embed view doubles again (now ~4x the admin size) for kiosk readability.
  const sizeCls = embed ? "h-48 w-48" : "h-12 w-12";
  const initialsCls = embed
    ? "text-5xl font-semibold text-muted-foreground"
    : "text-sm font-semibold text-muted-foreground";
  return (
    <div className={`relative shrink-0 overflow-hidden rounded-full bg-muted ${sizeCls}`}>
      {showImage ? (
        <img
          src={photoUrl}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        <span className={`flex h-full w-full items-center justify-center ${initialsCls}`}>
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

  // Doubled (again) sizing for /embed/birthdays — now ~4x the admin view so
  // the cards read clearly across the room on a 1080p signage display.
  const cls = {
    section: embed ? "p-24" : "p-6",
    titleRow: embed ? "mb-16" : "mb-4",
    title: embed ? "gap-8 text-6xl font-semibold" : "gap-2 text-lg font-semibold",
    titleIcon: embed ? "h-20 w-20 text-primary" : "h-5 w-5 text-primary",
    statusText: embed ? "text-4xl" : "text-sm",
    grid: embed
      ? "grid gap-12 sm:grid-cols-1 xl:grid-cols-2"
      : "grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4",
    tile: embed ? "gap-12 p-16" : "gap-3 p-4",
    nameRow: embed ? "gap-8" : "gap-2",
    name: embed ? "text-5xl font-semibold" : "text-sm font-semibold",
    badge: embed ? "text-2xl" : "text-xs",
    department: embed ? "text-3xl" : "text-xs",
    dateLine: embed ? "mt-4 text-3xl" : "mt-1 text-xs",
  };

  return (
    <section
      className={`rounded-xl bg-card text-card-foreground ring-1 ring-foreground/10 ${cls.section}`}
    >
      <div className={`flex items-center justify-between ${cls.titleRow}`}>
        <h2 className={`flex items-center ${cls.title}`}>
          <Cake className={cls.titleIcon} aria-hidden="true" />
          {t("hr.birthdays.title")}
        </h2>
      </div>

      {isLoading && (
        <p className={`text-muted-foreground ${cls.statusText}`}>
          {t("common.loading")}
        </p>
      )}

      {isError && (
        <p className={`text-destructive ${cls.statusText}`}>
          {t("hr.birthdays.error")}
        </p>
      )}

      {!isLoading && !isError && (data?.length ?? 0) === 0 && (
        <p className={`text-muted-foreground ${cls.statusText}`}>
          {t("hr.birthdays.empty")}
        </p>
      )}

      {!isLoading && !isError && (data?.length ?? 0) > 0 && (
        <ul className={cls.grid}>
          {(data ?? []).map((entry) => {
            const isToday = entry.weekday === today;
            return (
              <li
                key={entry.employee_id}
                className={
                  `flex items-start rounded-xl bg-card ring-1 ${cls.tile} ` +
                  (isToday
                    ? "ring-primary/40 bg-primary/5"
                    : "ring-foreground/10")
                }
              >
                <Avatar entry={entry} embed={embed} />
                <div className="min-w-0 flex-1">
                  <div className={`flex items-center ${cls.nameRow}`}>
                    <span className={`truncate ${cls.name}`}>
                      {displayName(entry)}
                    </span>
                    {isToday && (
                      <Badge variant="secondary" className={cls.badge}>
                        {t("hr.birthdays.today")}
                      </Badge>
                    )}
                  </div>
                  {entry.department && (
                    <p className={`truncate text-muted-foreground ${cls.department}`}>
                      {entry.department}
                    </p>
                  )}
                  <p className={`text-muted-foreground tabular-nums ${cls.dateLine}`}>
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
