/**
 * EmbedWorldCupPage — kiosk-friendly /embed/worldcup. Sibling of
 * EmbedBirthdaysPage: no admin shell, no auth, German default (?lang=en).
 * Polls the public worldcup feed at the server-configured interval and
 * fires a full-screen overlay when a score increases between polls.
 * No scrolling ever — the match grid auto-fits 1–6 matches.
 */
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  fetchWorldCupTodayPublic,
  type WorldCupFeed,
  type WorldCupMatch,
} from "@/lib/api";
import { detectGoals, type GoalEvent } from "@/components/worldcup/goalDetection";
import { MatchCard } from "@/components/worldcup/MatchCard";
import { GoalOverlay } from "@/components/worldcup/GoalOverlay";

const GOAL_OVERLAY_MS = 6000;
const DEFAULT_CYCLE_S = 30;

/** Post embed-cycle-complete only once the display time has elapsed AND no
 *  goal overlay is currently queued (so we never cut a goal animation off). */
export function shouldPostCycle(timerElapsed: boolean, goalQueueLength: number): boolean {
  return timerElapsed && goalQueueLength === 0;
}

function gridClass(count: number): string {
  if (count <= 1) return "grid-cols-1";
  if (count === 2) return "grid-cols-2";
  if (count <= 4) return "grid-cols-2 grid-rows-2";
  return "grid-cols-3 grid-rows-2";
}

export function EmbedWorldCupPage() {
  const { t, i18n } = useTranslation();
  useEffect(() => {
    const lang = new URLSearchParams(window.location.search).get("lang") ?? "de";
    if (i18n.language !== lang) {
      void i18n.changeLanguage(lang);
    }
  }, [i18n]);

  const [refreshMs, setRefreshMs] = useState(60_000);
  const { data } = useQuery<WorldCupFeed>({
    queryKey: ["worldcup", "embed-today"],
    queryFn: fetchWorldCupTodayPublic,
    refetchInterval: refreshMs,
    refetchIntervalInBackground: true,
  });

  // Score diff between polls → goal overlay queue (sequential playback).
  const prevRef = useRef<Map<number, WorldCupMatch> | null>(null);
  const [goalQueue, setGoalQueue] = useState<GoalEvent[]>([]);

  useEffect(() => {
    if (!data) return;
    setRefreshMs(Math.max(30, data.refresh_seconds) * 1000);
    const events = detectGoals(prevRef.current, data.matches);
    if (events.length > 0) setGoalQueue((q) => [...q, ...events]);
    prevRef.current = new Map(data.matches.map((m) => [m.id, m]));
  }, [data]);

  const currentGoal = goalQueue[0] ?? null;
  useEffect(() => {
    if (!currentGoal) return;
    const timer = setTimeout(() => setGoalQueue((q) => q.slice(1)), GOAL_OVERLAY_MS);
    return () => clearTimeout(timer);
  }, [currentGoal]);

  const [timerElapsed, setTimerElapsed] = useState(false);
  const postedRef = useRef(false);
  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get("duration");
    const parsed = raw != null ? parseInt(raw, 10) : NaN;
    const seconds = Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_CYCLE_S;
    const id = window.setTimeout(() => setTimerElapsed(true), seconds * 1000);
    return () => window.clearTimeout(id);
  }, []);
  useEffect(() => {
    if (postedRef.current) return;
    if (shouldPostCycle(timerElapsed, goalQueue.length)) {
      postedRef.current = true;
      try {
        window.parent.postMessage({ type: "embed-cycle-complete" }, "*");
      } catch {
        /* cross-origin post can throw — harmless when standalone */
      }
    }
  }, [timerElapsed, goalQueue.length]);

  const matches = data?.matches ?? [];
  const staleTime = data?.stale_since
    ? new Date(data.stale_since).toLocaleTimeString(i18n.language, {
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <div className="h-screen w-screen overflow-hidden bg-background flex flex-col p-6 gap-4">
      <header className="flex items-baseline justify-between shrink-0">
        <h1 className="text-3xl font-bold">{t("worldcup.title")}</h1>
        <div className="flex items-baseline gap-4">
          {staleTime && (
            <span className="text-sm text-muted-foreground">
              {t("worldcup.stale", { time: staleTime })}
            </span>
          )}
          <span className="text-3xl font-medium text-muted-foreground">
            {new Date().toLocaleDateString(i18n.language, {
              weekday: "long",
              day: "numeric",
              month: "long",
            })}
          </span>
        </div>
      </header>

      {matches.length > 0 ? (
        <div className={`grid flex-1 min-h-0 gap-4 ${gridClass(matches.length)}`}>
          {matches.map((m) => (
            <MatchCard key={m.id} match={m} />
          ))}
        </div>
      ) : (
        <EmptyState feed={data} />
      )}

      {currentGoal && <GoalOverlay goal={currentGoal} />}
    </div>
  );
}

function EmptyState({ feed }: { feed: WorldCupFeed | undefined }) {
  const { t, i18n } = useTranslation();
  if (!feed) return null;
  const headline =
    feed.error === "not_configured"
      ? t("worldcup.not_configured")
      : t("worldcup.no_matches");
  const nextDate = feed.next_matchday
    ? new Date(feed.next_matchday).toLocaleDateString(i18n.language, {
        weekday: "long",
        day: "numeric",
        month: "long",
      })
    : null;
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-8 min-h-0">
      <p className="text-5xl font-semibold text-center">{headline}</p>
      {nextDate && (
        <>
          <p className="text-2xl text-muted-foreground">
            {t("worldcup.next_matchday", { date: nextDate })}
          </p>
          <div className="grid grid-cols-3 gap-3">
            {feed.next_matches.slice(0, 6).map((m) => (
              <MatchCard key={m.id} match={m} compact />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
