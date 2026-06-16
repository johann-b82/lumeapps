/**
 * EmbedWorldCupKnockoutPage — kiosk /embed/worldcup/knockout.
 * One column per knockout stage. Single page; useEmbedPaging(1,1) drives
 * the lifetime. Empty (group stage) → calm "noch nicht entschieden".
 */
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  fetchWorldCupKnockoutPublic,
  type KnockoutFeed,
  type WorldCupMatch,
} from "@/lib/api";
import { TeamFlag } from "@/components/worldcup/TeamFlag";
import { useEmbedPaging } from "@/components/dashboard/useEmbedPaging";

const STAGE_KEY: Record<string, string> = {
  LAST_32: "worldcup.stage.last_32",
  LAST_16: "worldcup.stage.last_16",
  QUARTER_FINALS: "worldcup.stage.quarter",
  SEMI_FINALS: "worldcup.stage.semi",
  THIRD_PLACE: "worldcup.stage.third",
  FINAL: "worldcup.stage.final",
};

function Pairing({ m }: { m: WorldCupMatch }) {
  const { i18n } = useTranslation();
  const started = m.status !== "SCHEDULED" && m.status !== "TIMED";
  const right = started
    ? `${m.score_home ?? 0}:${m.score_away ?? 0}`
    : new Date(m.kickoff_utc).toLocaleString(i18n.language, { weekday: "short", hour: "2-digit", minute: "2-digit" });
  return (
    <div className="flex items-center justify-between gap-2 py-2 border-b border-border/50 last:border-0 text-lg">
      <span className="flex items-center gap-1 min-w-0">
        <TeamFlag team={m.home} className="h-4 w-6" /><span className="truncate">{m.home.short_name ?? m.home.name}</span>
        <span className="text-muted-foreground">–</span>
        <TeamFlag team={m.away} className="h-4 w-6" /><span className="truncate">{m.away.short_name ?? m.away.name}</span>
      </span>
      <span className="font-semibold tabular-nums whitespace-nowrap">{right}</span>
    </div>
  );
}

export function EmbedWorldCupKnockoutPage() {
  const { t, i18n } = useTranslation();
  useEffect(() => {
    const lang = new URLSearchParams(window.location.search).get("lang") ?? "de";
    if (i18n.language !== lang) void i18n.changeLanguage(lang);
  }, [i18n]);

  const { data } = useQuery<KnockoutFeed>({
    queryKey: ["worldcup", "embed-knockout"],
    queryFn: fetchWorldCupKnockoutPublic,
    refetchInterval: (q) => Math.max(30, q.state.data?.refresh_seconds ?? 60) * 1000,
    refetchIntervalInBackground: true,
  });
  useEmbedPaging(1, 1);

  const stages = data?.stages ?? [];

  return (
    <div className="h-screen w-screen overflow-hidden bg-background flex flex-col p-6 gap-4">
      <h1 className="text-3xl font-bold shrink-0">{t("worldcup.knockout_title")}</h1>
      {stages.length > 0 ? (
        <div className="grid flex-1 min-h-0 gap-4" style={{ gridTemplateColumns: `repeat(${stages.length}, minmax(0, 1fr))` }}>
          {stages.map((s) => (
            <div key={s.stage} className="rounded-2xl border-2 border-border bg-card p-4 flex flex-col min-h-0 overflow-hidden">
              <div className="text-xl font-semibold mb-2 shrink-0">{t(STAGE_KEY[s.stage] ?? s.stage)}</div>
              <div className="flex-1 min-h-0">{s.matches.map((m) => <Pairing key={m.id} m={m} />)}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-4xl text-muted-foreground">
          {t("worldcup.knockout_pending")}
        </div>
      )}
    </div>
  );
}
