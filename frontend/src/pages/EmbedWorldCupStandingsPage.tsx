/**
 * EmbedWorldCupStandingsPage — kiosk /embed/worldcup/standings.
 * Shows the 12 group tables 6-per-page via useEmbedPaging; the player drives
 * per-page time with ?duration and advances on embed-cycle-complete.
 */
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { fetchWorldCupStandingsPublic, type StandingsFeed } from "@/lib/api";
import { TeamFlag } from "@/components/worldcup/TeamFlag";
import { useEmbedPaging } from "@/components/dashboard/useEmbedPaging";

const PAGE_SIZE = 6;

export function EmbedWorldCupStandingsPage() {
  const { t, i18n } = useTranslation();
  useEffect(() => {
    const lang = new URLSearchParams(window.location.search).get("lang") ?? "de";
    if (i18n.language !== lang) void i18n.changeLanguage(lang);
  }, [i18n]);

  const { data } = useQuery<StandingsFeed>({
    queryKey: ["worldcup", "embed-standings"],
    queryFn: fetchWorldCupStandingsPublic,
    refetchInterval: (q) => Math.max(30, q.state.data?.refresh_seconds ?? 60) * 1000,
    refetchIntervalInBackground: true,
  });

  const groups = data?.groups ?? [];
  const { page } = useEmbedPaging(Math.max(groups.length, 1), PAGE_SIZE);
  const shown = groups.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  return (
    <div className="h-screen w-screen overflow-hidden bg-background flex flex-col p-6 gap-4">
      <h1 className="text-3xl font-bold shrink-0">{t("worldcup.standings_title")}</h1>
      <div className="grid flex-1 min-h-0 grid-cols-3 grid-rows-2 gap-4">
        {shown.map((g) => (
          <div key={g.group} className="rounded-2xl border-2 border-border bg-card p-3 flex flex-col min-h-0">
            <div className="text-xl font-semibold mb-2">{g.group}</div>
            <table className="w-full text-lg tabular-nums">
              <tbody>
                {g.table.map((r) => (
                  <tr key={r.position} className="border-b border-border/50 last:border-0">
                    <td className="py-1 pr-2 text-muted-foreground">{r.position}</td>
                    <td className="py-1 pr-2"><TeamFlag team={r.team} className="h-4 w-6 inline-block" /></td>
                    <td className="py-1 truncate">{r.team.name}</td>
                    <td className="py-1 px-1 text-center text-muted-foreground">{r.played}</td>
                    <td className="py-1 px-1 text-center text-muted-foreground">{r.goal_difference > 0 ? `+${r.goal_difference}` : r.goal_difference}</td>
                    <td className="py-1 pl-1 text-right font-semibold">{r.points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}
