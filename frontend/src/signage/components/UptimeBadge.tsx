import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import type { SignageDeviceAnalytics } from "@/signage/lib/signageTypes";

/**
 * Phase 53 SGN-ANA-01 — per-device uptime / missed-windows badge.
 *
 * Two variants (uptime / missed) share tier logic so a row's two badges
 * always agree in colour. Threshold boundaries per D-13:
 *   pct ≥ 95 → green, 80 ≤ pct < 95 → amber, pct < 80 → red,
 *   pct === null (zero heartbeats ever) → neutral '—'.
 *
 * className-override pattern mirrors DeviceStatusChip (no new shadcn variant,
 * no dark-mode classes — hard gate 3 stays clean because frontend/src/signage/**
 * is scanned by check-signage-invariants.mjs).
 *
 * Tooltip uses native `title=` on a wrapping span (no Radix Tooltip in this
 * repo — see 53-RESEARCH.md §Pattern 8). Literal numerator/denominator per
 * D-15. DE/EN parity driven by i18n.
 */
export type UptimeTier = "green" | "amber" | "red" | "neutral";

export function uptimeTier(pct: number | null): UptimeTier {
  if (pct === null) return "neutral";
  if (pct >= 95) return "green";
  if (pct >= 80) return "amber";
  return "red";
}

const CLASS_MAP: Record<UptimeTier, string> = {
  green: "bg-green-100 text-green-800",
  amber: "bg-amber-100 text-amber-800",
  red: "bg-red-100 text-red-800",
  neutral: "bg-muted text-muted-foreground",
};

export interface UptimeBadgeProps {
  variant: "uptime" | "missed";
  data: SignageDeviceAnalytics | undefined;
}

export function UptimeBadge({ variant, data }: UptimeBadgeProps) {
  const { t } = useTranslation();
  const noData = data === undefined || data.uptime_24h_pct === null;
  const tier: UptimeTier = noData ? "neutral" : uptimeTier(data!.uptime_24h_pct);
  const label = noData
    ? "—"
    : variant === "uptime"
      ? `${data!.uptime_24h_pct!.toFixed(1)}%`
      : String(data!.missed_windows_24h);

  let tooltip: string;
  if (noData) {
    tooltip = t("signage.admin.device.analytics.badge.noData");
  } else {
    const partial = data!.window_minutes < 1440;
    const buckets = data!.window_minutes - data!.missed_windows_24h;
    const denom = data!.window_minutes;
    const windowH = Math.ceil(data!.window_minutes / 60);
    if (variant === "uptime") {
      tooltip = partial
        ? t("signage.admin.device.analytics.uptime24h.tooltip_partial", {
            buckets,
            denom,
            windowH,
          })
        : t("signage.admin.device.analytics.uptime24h.tooltip", {
            buckets,
            denom,
          });
    } else {
      tooltip = partial
        ? t("signage.admin.device.analytics.missed24h.tooltip_partial", {
            missed: data!.missed_windows_24h,
            windowH,
          })
        : t("signage.admin.device.analytics.missed24h.tooltip", {
            missed: data!.missed_windows_24h,
          });
    }
  }

  return (
    <span title={tooltip} className="inline-block">
      <Badge className={CLASS_MAP[tier]}>{label}</Badge>
    </span>
  );
}
