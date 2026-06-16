import type { WorldCupTeam } from "@/lib/api";

/** Country flag/crest from football-data.org. Empty box when no crest so
 *  layout stays stable (no broken-image icon on the signage screen). */
export function TeamFlag({ team, className = "h-5 w-7" }: { team: WorldCupTeam; className?: string }) {
  if (!team.crest) return <div className={`${className} shrink-0`} aria-hidden="true" />;
  return <img src={team.crest} alt="" className={`${className} object-contain shrink-0`} />;
}
