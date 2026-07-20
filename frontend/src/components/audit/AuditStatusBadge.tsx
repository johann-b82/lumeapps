/**
 * Status + progress chrome for the Audit-Modul.
 *
 * Follows the tier-function + class-map + Badge pattern already used by
 * signage/components/UptimeBadge.tsx. Status colours are intentionally
 * invariant across light/dark (no `dark:` variants): the meaning of "overdue"
 * must not shift with the theme.
 */
import { Badge } from "@/components/ui/badge";
import { useTranslation } from "react-i18next";
import type { AuditStatus, PhaseStatus } from "@/lib/auditApi";

type Tier = "neutral" | "progress" | "done" | "warn" | "muted";

const CLASS_MAP: Record<Tier, string> = {
  neutral: "bg-slate-100 text-slate-800",
  progress: "bg-blue-100 text-blue-800",
  done: "bg-green-100 text-green-800",
  warn: "bg-red-100 text-red-800",
  muted: "bg-muted text-muted-foreground",
};

const AUDIT_TIER: Record<AuditStatus, Tier> = {
  geplant: "neutral",
  in_vorbereitung: "neutral",
  in_durchfuehrung: "progress",
  berichtet: "progress",
  massnahmen_offen: "warn",
  abgeschlossen: "done",
  verschoben: "muted",
  abgesagt: "muted",
};

const PHASE_TIER: Record<PhaseStatus, Tier> = {
  offen: "neutral",
  in_arbeit: "progress",
  erledigt: "done",
  nicht_zutreffend: "muted",
};

export function AuditStatusBadge({ status }: { status: AuditStatus }) {
  const { t } = useTranslation();
  return (
    <Badge className={CLASS_MAP[AUDIT_TIER[status] ?? "neutral"]}>
      {t(`audit.status.${status}`)}
    </Badge>
  );
}

export function PhaseStatusBadge({ status }: { status: PhaseStatus }) {
  const { t } = useTranslation();
  return (
    <Badge className={CLASS_MAP[PHASE_TIER[status] ?? "neutral"]}>
      {t(`audit.phaseStatus.${status}`)}
    </Badge>
  );
}

export function OverdueBadge() {
  const { t } = useTranslation();
  return <Badge className={CLASS_MAP.warn}>{t("audit.overdue")}</Badge>;
}

/**
 * "6 / 10" plus a bar. `percent` is computed by the backend over the phases
 * that are actually relevant (n.z. phases are excluded from the denominator),
 * so a fully-handled audit reaches 100% even with skipped phases.
 */
export function ProgressBar({
  done,
  relevant,
  percent,
  overdue,
}: {
  done: number;
  relevant: number;
  percent: number;
  overdue: boolean;
}) {
  return (
    <div className="flex items-center gap-2 min-w-[140px]">
      <div
        className="h-2 flex-1 rounded-full bg-muted overflow-hidden"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`h-full rounded-full transition-all ${
            overdue ? "bg-red-500" : percent === 100 ? "bg-green-500" : "bg-blue-500"
          }`}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-muted-foreground whitespace-nowrap">
        {done} / {relevant}
      </span>
    </div>
  );
}
