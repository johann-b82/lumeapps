/**
 * EmbedWorldCupMatchesPage — kiosk /embed/worldcup/matches.
 * Three columns: gestern / heute / morgen. Single page; useEmbedPaging(1,1)
 * posts embed-cycle-complete after ?duration so the player advances.
 */
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  fetchWorldCupMatchesPublic,
  type MatchesWindowFeed,
  type WorldCupMatch,
} from "@/lib/api";
import { TeamFlag } from "@/components/worldcup/TeamFlag";
import { useEmbedPaging } from "@/components/dashboard/useEmbedPaging";

function MatchChip({ m }: { m: WorldCupMatch }) {
  const { i18n } = useTranslation();
  const started = m.status !== "SCHEDULED" && m.status !== "TIMED";
  const live = m.status === "IN_PLAY" || m.status === "PAUSED";
  const right = started
    ? `${m.score_home ?? 0}:${m.score_away ?? 0}`
    : new Date(m.kickoff_utc).toLocaleTimeString(i18n.language, { hour: "2-digit", minute: "2-digit" });
  return (
    <div className="flex items-center gap-4 rounded-2xl border-2 border-border bg-card px-6 py-4 text-3xl">
      <TeamFlag team={m.home} className="h-9 w-14" />
      <span className="truncate max-w-[7ch]">{m.home.short_name ?? m.home.name}</span>
      <span className={`font-bold tabular-nums px-2 ${live ? "text-destructive animate-pulse" : ""}`}>{right}</span>
      <span className="truncate max-w-[7ch]">{m.away.short_name ?? m.away.name}</span>
      <TeamFlag team={m.away} className="h-9 w-14" />
    </div>
  );
}

// One full-width horizontal band per day; matches flow left-to-right as chips.
function DayBand({ title, matches }: { title: string; matches: WorldCupMatch[] }) {
  const { t } = useTranslation();
  return (
    <div className="flex-1 min-h-0 rounded-2xl border-2 border-border bg-card/40 p-5 flex flex-col gap-3 overflow-hidden">
      <div className="text-3xl font-semibold shrink-0">{title}</div>
      {matches.length > 0 ? (
        <div className="flex flex-wrap gap-4 content-start overflow-hidden">
          {matches.map((m) => <MatchChip key={m.id} m={m} />)}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-muted-foreground text-3xl">
          {t("worldcup.no_matches")}
        </div>
      )}
    </div>
  );
}

export function EmbedWorldCupMatchesPage() {
  const { t, i18n } = useTranslation();
  useEffect(() => {
    const lang = new URLSearchParams(window.location.search).get("lang") ?? "de";
    if (i18n.language !== lang) void i18n.changeLanguage(lang);
  }, [i18n]);

  const { data } = useQuery<MatchesWindowFeed>({
    queryKey: ["worldcup", "embed-matches"],
    queryFn: fetchWorldCupMatchesPublic,
    refetchInterval: (q) => Math.max(30, q.state.data?.refresh_seconds ?? 60) * 1000,
    refetchIntervalInBackground: true,
  });
  useEmbedPaging(1, 1);

  return (
    <div className="h-screen w-screen overflow-hidden bg-background flex flex-col p-6 gap-4">
      <h1 className="text-4xl font-bold shrink-0">{t("worldcup.matches_title")}</h1>
      <div className="flex flex-col flex-1 min-h-0 gap-4">
        <DayBand title={t("worldcup.yesterday")} matches={data?.yesterday ?? []} />
        <DayBand title={t("worldcup.today")} matches={data?.today ?? []} />
        <DayBand title={t("worldcup.tomorrow")} matches={data?.tomorrow ?? []} />
      </div>
    </div>
  );
}
