import type { WorldCupMatch, WorldCupTeam } from "@/lib/api";

export interface GoalEvent {
  matchId: number;
  team: WorldCupTeam;
  scoreHome: number;
  scoreAway: number;
}

/**
 * Diff scores between two polls. prev === null means "first poll after page
 * load" — never fire then, or a kiosk restart would replay old goals.
 * Matches absent from prev (e.g. day rollover) are skipped for the same
 * reason. Downward corrections (upstream fixing a wrong score) are ignored.
 */
export function detectGoals(
  prev: Map<number, WorldCupMatch> | null,
  next: WorldCupMatch[],
): GoalEvent[] {
  if (!prev) return [];
  const events: GoalEvent[] = [];
  for (const match of next) {
    const before = prev.get(match.id);
    if (!before) continue;
    const prevHome = before.score_home ?? 0;
    const prevAway = before.score_away ?? 0;
    const nextHome = match.score_home ?? 0;
    const nextAway = match.score_away ?? 0;
    if (nextHome > prevHome) {
      events.push({ matchId: match.id, team: match.home, scoreHome: nextHome, scoreAway: nextAway });
    }
    if (nextAway > prevAway) {
      events.push({ matchId: match.id, team: match.away, scoreHome: nextHome, scoreAway: nextAway });
    }
  }
  return events;
}
