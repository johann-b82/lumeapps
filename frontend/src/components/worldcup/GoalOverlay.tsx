import { useTranslation } from "react-i18next";
import type { GoalEvent } from "./goalDetection";

/** Full-screen goal celebration. Parent mounts/unmounts it on a timer. */
export function GoalOverlay({ goal }: { goal: GoalEvent }) {
  const { t } = useTranslation();
  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-8 bg-background/95 worldcup-goal-pop">
      <span className="text-[9rem] leading-none font-black tracking-tight worldcup-goal-flash">
        ⚽ {t("worldcup.goal")}
      </span>
      {goal.team.crest && (
        <img src={goal.team.crest} alt="" className="h-40 w-40 object-contain" />
      )}
      <span className="text-6xl font-bold">{goal.team.name}</span>
      <span className="text-7xl font-bold tabular-nums">
        {goal.scoreHome} : {goal.scoreAway}
      </span>
    </div>
  );
}
