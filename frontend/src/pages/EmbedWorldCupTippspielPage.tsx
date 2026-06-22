/**
 * EmbedWorldCupTippspielPage — kiosk /embed/worldcup/tippspiel.
 * Internal department betting game: ranking by total points over all played
 * matches. Single page; useEmbedPaging(1,1) posts embed-cycle-complete so the
 * signage player advances.
 */
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { fetchWorldCupTippspielPublic, type TippspielFeed } from "@/lib/api";
import { useEmbedPaging } from "@/components/dashboard/useEmbedPaging";

export function EmbedWorldCupTippspielPage() {
  const { t, i18n } = useTranslation();
  useEffect(() => {
    const lang = new URLSearchParams(window.location.search).get("lang") ?? "de";
    if (i18n.language !== lang) void i18n.changeLanguage(lang);
  }, [i18n]);

  const { data } = useQuery<TippspielFeed>({
    queryKey: ["worldcup", "embed-tippspiel"],
    queryFn: fetchWorldCupTippspielPublic,
    refetchInterval: (q) => Math.max(30, q.state.data?.refresh_seconds ?? 60) * 1000,
    refetchIntervalInBackground: true,
  });
  useEmbedPaging(1, 1);

  const rows = data?.ranking ?? [];

  return (
    <div className="h-screen w-screen overflow-hidden bg-background flex flex-col p-8 gap-6">
      <h1 className="text-5xl font-bold shrink-0">{t("worldcup.tippspiel_title")}</h1>
      <div className="flex-1 min-h-0 overflow-hidden">
        <table className="w-full text-4xl tabular-nums">
          <thead>
            <tr className="text-3xl text-muted-foreground border-b-2 border-border">
              <th className="text-left py-4 w-28">{t("worldcup.tippspiel.rank")}</th>
              <th className="text-left py-4">{t("worldcup.tippspiel.department")}</th>
              <th className="text-right py-4 px-6">{t("worldcup.tippspiel.last")}</th>
              <th className="text-right py-4">{t("worldcup.tippspiel.total")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.department}
                className="border-b border-border/50 last:border-0"
              >
                <td className="py-7 font-bold">{r.rank}</td>
                <td className="py-7 truncate pr-6">{r.department}</td>
                <td className="py-7 text-right px-6 text-muted-foreground">
                  +{r.last_points}
                </td>
                <td className="py-7 text-right font-bold">{r.total_points}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && (
          <p className="text-3xl text-muted-foreground mt-8">
            {t("worldcup.tippspiel.empty")}
          </p>
        )}
      </div>
    </div>
  );
}
