import { useTranslation } from "react-i18next";
import type { SensorStatusEntry } from "@/lib/api";

/**
 * SensorHealthChip — DIFF-10. Small pill that surfaces the liveness
 * decision made server-side in `/api/sensors/status` (3 consecutive
 * failures → offline).
 *
 * D-14: token-only coloring — `bg-primary/10 text-primary` for OK,
 * `bg-destructive/10 text-destructive` for offline, `bg-muted
 * text-muted-foreground` for unknown. No hex, no theme-variant classes.
 */

export interface SensorHealthChipProps {
  status: SensorStatusEntry | undefined;
}

interface DurationParts {
  count: number;
  unit: "seconds" | "minutes" | "hours" | "days";
}

function formatDurationParts(ms: number): DurationParts {
  const s = Math.max(0, Math.floor(ms / 1000));
  if (s < 60) return { count: s, unit: "seconds" };
  const m = Math.floor(s / 60);
  if (m < 60) return { count: m, unit: "minutes" };
  const h = Math.floor(m / 60);
  if (h < 24) return { count: h, unit: "hours" };
  const d = Math.floor(h / 24);
  return { count: d, unit: "days" };
}

export function SensorHealthChip({ status }: SensorHealthChipProps) {
  const { t } = useTranslation();

  if (!status) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground">
        {t("sensors.status.unknown")}
      </span>
    );
  }

  // Online path: measure "ok since last_success_at".
  // Offline path: measure "offline since last_attempt_at" (first failed attempt).
  const isOffline = status.offline;
  const anchorIso = isOffline
    ? status.last_attempt_at ?? status.last_success_at
    : status.last_success_at ?? status.last_attempt_at;

  if (!anchorIso) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground">
        {t("sensors.status.unknown")}
      </span>
    );
  }

  const anchorMs = new Date(anchorIso).getTime();
  if (!Number.isFinite(anchorMs)) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground">
        {t("sensors.status.unknown")}
      </span>
    );
  }

  const parts = formatDurationParts(Date.now() - anchorMs);
  const duration = t(`sensors.duration.${parts.unit}`, { count: parts.count });

  if (isOffline) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-destructive/10 text-destructive">
        {t("sensors.status.offlineSince", { duration })}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-primary/10 text-primary">
      {t("sensors.status.okSince", { duration })}
    </span>
  );
}
