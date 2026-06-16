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

function MatchRow({ m }: { m: WorldCupMatch }) {
  const { i18n } = useTranslation();
  const started = m.status !== "SCHEDULED" && m.status !== "TIMED";
  const live = m.status === "IN_PLAY" || m.status === "PAUSED";
  const right = started
    ? `${m.score_home ?? 0}:${m.score_away ?? 0}`
    : new Date(m.kickoff_utc).toLocaleTimeString(i18n.language, { hour: "2-digit", minute: "2-digit" });
  return (
    <div className="flex items-center justify-between gap-2 py-2 border-b border-border/50 last:border-0 text-xl">
      <span className="flex items-center gap-2 min-w-0">
        <TeamFlag team={m.home} className="h-4 w-6" />
        <span className="truncate">{m.home.short_name ?? m.home.name}</span>
        <span className="text-muted-foreground">–</span>
        <TeamFlag team={m.away} className="h-4 w-6" />
        <span className="truncate">{m.away.short_name ?? m.away.name}</span>
      </span>
      <span className={`font-semibold tabular-nums ${live ? "text-destructive animate-pulse" : ""}`}>{right}</span>
    </div>
  );
}

function Column({ title, matches }: { title: string; matches: WorldCupMatch[] }) {
  const { t } = useTranslation();
  return (
    <div className="rounded-2xl border-2 border-border bg-card p-4 flex flex-col min-h-0 overflow-hidden">
      <div className="text-2xl font-semibold mb-2 shrink-0">{title}</div>
      {matches.length > 0 ? (
        <div className="flex-1 min-h-0">{matches.map((m) => <MatchRow key={m.id} m={m} />)}</div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-muted-foreground">{t("worldcup.no_matches")}</div>
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
      <h1 className="text-3xl font-bold shrink-0">{t("worldcup.matches_title")}</h1>
      <div className="grid flex-1 min-h-0 grid-cols-3 gap-4">
        <Column title={t("worldcup.yesterday")} matches={data?.yesterday ?? []} />
        <Column title={t("worldcup.today")} matches={data?.today ?? []} />
        <Column title={t("worldcup.tomorrow")} matches={data?.tomorrow ?? []} />
      </div>
    </div>
  );
}
