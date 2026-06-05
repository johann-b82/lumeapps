/**
 * JoinersCard — active employees hired in the last 6 weeks, for the HR
 * landing and the /embed/joiners signage view.
 *
 * Mirrors BirthdaysCard exactly in chrome, scaling and embed contract so
 * the two cards read as one design at two scales. Different data source,
 * different per-row label (hire date + days-with-company instead of
 * birthday weekday). Sorted newest-hire-first.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Sparkles } from "lucide-react";

import {
  fetchJoinersRecent,
  fetchJoinersRecentPublic,
  type JoinerEntry,
} from "@/lib/api";
import { hrKpiKeys } from "@/lib/queryKeys";
import { Badge } from "@/components/ui/badge";
import { useEmbedPaging } from "./useEmbedPaging";

const EMBED_PAGE_SIZE = 2;

interface JoinersCardProps {
  /** Switch to the unauthenticated mirror for the /embed/joiners kiosk view. */
  embed?: boolean;
}

function displayName(e: JoinerEntry): string {
  const parts = [e.first_name, e.last_name].filter((p): p is string => !!p);
  return parts.length ? parts.join(" ") : `#${e.employee_id}`;
}

function initials(e: JoinerEntry): string {
  const f = (e.first_name ?? "").trim()[0] ?? "";
  const l = (e.last_name ?? "").trim()[0] ?? "";
  const combined = (f + l).toUpperCase();
  return combined || "?";
}

function Avatar({ entry, embed }: { entry: JoinerEntry; embed: boolean }) {
  const [failed, setFailed] = useState(false);
  const showImage = entry.has_photo && !failed;
  const photoUrl = embed
    ? `/api/hr/embed/employees/${entry.employee_id}/photo`
    : `/api/hr/employees/${entry.employee_id}/photo`;
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

export function JoinersCard({ embed = false }: JoinersCardProps = {}) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";

  const { data, isLoading, isError } = useQuery({
    queryKey: embed
      ? [...hrKpiKeys.joinersRecent(), "embed"]
      : hrKpiKeys.joinersRecent(),
    queryFn: embed ? fetchJoinersRecentPublic : fetchJoinersRecent,
    staleTime: 30 * 60_000,
  });

  const paging = useEmbedPaging(data?.length ?? 0, EMBED_PAGE_SIZE);

  const formatDay = (iso: string) =>
    new Intl.DateTimeFormat(locale, { day: "numeric", month: "long" }).format(
      new Date(iso + "T00:00:00"),
    );

  // Same scaling table as BirthdaysCard so the two read as one design.
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
          <Sparkles className={cls.titleIcon} aria-hidden="true" />
          {t("hr.joiners.title")}
        </h2>
      </div>

      {isLoading && (
        <p className={`text-muted-foreground ${cls.statusText}`}>
          {t("common.loading")}
        </p>
      )}

      {isError && (
        <p className={`text-destructive ${cls.statusText}`}>
          {t("hr.joiners.error")}
        </p>
      )}

      {!isLoading && !isError && (data?.length ?? 0) === 0 && (
        <p className={`text-muted-foreground ${cls.statusText}`}>
          {t("hr.joiners.empty")}
        </p>
      )}

      {!isLoading && !isError && (data?.length ?? 0) > 0 && (
        <ul className={cls.grid}>
          {(embed
            ? (data ?? []).slice(
                paging.page * EMBED_PAGE_SIZE,
                paging.page * EMBED_PAGE_SIZE + EMBED_PAGE_SIZE,
              )
            : (data ?? [])
          ).map((entry) => {
            // Day-0 joiners (started today) get the highlight + Today badge.
            const isToday = entry.days_with_company === 0;
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
                        {t("hr.joiners.today")}
                      </Badge>
                    )}
                  </div>
                  {entry.department && (
                    <p className={`truncate text-muted-foreground ${cls.department}`}>
                      {entry.department}
                    </p>
                  )}
                  <p className={`text-muted-foreground tabular-nums ${cls.dateLine}`}>
                    {t("hr.joiners.since_date", { date: formatDay(entry.hire_date) })}
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
