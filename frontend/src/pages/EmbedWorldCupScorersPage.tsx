/**
 * EmbedWorldCupScorersPage — kiosk /embed/worldcup/scorers.
 * Top 10 in two columns of 5. Single page; useEmbedPaging(1,1) drives lifetime.
 */
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { fetchWorldCupScorersPublic, type ScorersFeed } from "@/lib/api";
import { TeamFlag } from "@/components/worldcup/TeamFlag";
import { useEmbedPaging } from "@/components/dashboard/useEmbedPaging";

export function EmbedWorldCupScorersPage() {
  const { t, i18n } = useTranslation();
  useEffect(() => {
    const lang = new URLSearchParams(window.location.search).get("lang") ?? "de";
    if (i18n.language !== lang) void i18n.changeLanguage(lang);
  }, [i18n]);

  const { data } = useQuery<ScorersFeed>({
    queryKey: ["worldcup", "embed-scorers"],
    queryFn: fetchWorldCupScorersPublic,
    refetchInterval: (q) => Math.max(30, q.state.data?.refresh_seconds ?? 60) * 1000,
    refetchIntervalInBackground: true,
  });
  useEmbedPaging(1, 1);

  const scorers = data?.scorers ?? [];

  return (
    <div className="h-screen w-screen overflow-hidden bg-background flex flex-col p-6 gap-4">
      <h1 className="text-3xl font-bold shrink-0">{t("worldcup.scorers_title")}</h1>
      <div className="grid flex-1 min-h-0 grid-cols-2 gap-x-12 gap-y-1 content-start text-2xl overflow-hidden">
        {scorers.map((s) => (
          <div key={s.rank} className="flex items-center gap-3 py-2 border-b border-border/50">
            <span className="text-muted-foreground w-8 tabular-nums">{s.rank}.</span>
            <TeamFlag team={s.team} className="h-5 w-7" />
            <span className="truncate flex-1">{s.player_name}</span>
            <span className="font-bold tabular-nums">{s.goals}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
