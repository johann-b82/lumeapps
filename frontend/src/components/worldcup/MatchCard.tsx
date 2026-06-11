import { useTranslation } from "react-i18next";
import type { WorldCupMatch, WorldCupTeam } from "@/lib/api";

const LIVE_STATUSES = new Set(["IN_PLAY", "PAUSED"]);

function TeamBlock({ team, compact }: { team: WorldCupTeam; compact: boolean }) {
  const size = compact ? "h-10 w-10" : "h-24 w-24";
  return (
    <div className="flex flex-col items-center gap-2 min-w-0 flex-1">
      {team.crest ? (
        <img src={team.crest} alt="" className={`${size} object-contain`} />
      ) : (
        <div className={size} />
      )}
      <span className={`${compact ? "text-sm" : "text-2xl"} font-semibold text-center truncate w-full`}>
        {team.name}
      </span>
    </div>
  );
}

function StatusBadge({ match }: { match: WorldCupMatch }) {
  const { t, i18n } = useTranslation();
  if (match.status === "FINISHED") {
    return <span className="text-muted-foreground font-medium">{t("worldcup.ft")}</span>;
  }
  if (match.status === "PAUSED") {
    return <span className="text-primary font-semibold">{t("worldcup.ht")}</span>;
  }
  if (LIVE_STATUSES.has(match.status)) {
    return (
      <span className="flex items-center gap-2 text-destructive font-semibold animate-pulse">
        ● {match.minute != null ? `${match.minute}'` : t("worldcup.live")}
      </span>
    );
  }
  return (
    <span className="text-muted-foreground font-medium">
      {new Date(match.kickoff_utc).toLocaleTimeString(i18n.language, {
        hour: "2-digit",
        minute: "2-digit",
      })}
    </span>
  );
}

export function MatchCard({ match, compact = false }: { match: WorldCupMatch; compact?: boolean }) {
  const live = LIVE_STATUSES.has(match.status);
  const notStarted = match.status === "SCHEDULED" || match.status === "TIMED";
  const score = notStarted ? "– : –" : `${match.score_home ?? 0} : ${match.score_away ?? 0}`;
  return (
    <div
      className={`flex items-center justify-between rounded-2xl border-2 bg-card p-4 min-h-0 overflow-hidden ${
        live ? "border-destructive" : "border-border"
      }`}
    >
      <TeamBlock team={match.home} compact={compact} />
      <div className="flex flex-col items-center gap-2 px-4 shrink-0">
        <span className={`${compact ? "text-2xl" : "text-6xl"} font-bold tabular-nums whitespace-nowrap`}>
          {score}
        </span>
        <StatusBadge match={match} />
      </div>
      <TeamBlock team={match.away} compact={compact} />
    </div>
  );
}
