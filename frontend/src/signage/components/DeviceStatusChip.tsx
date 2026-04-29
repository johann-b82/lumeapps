import { useTranslation } from "react-i18next";
import { differenceInMinutes } from "date-fns";

import { Badge } from "@/components/ui/badge";

export interface DeviceStatusChipProps {
  /** ISO-8601 timestamp of the device's last heartbeat, or null if unseen. */
  lastSeenAt: string | null;
}

type Status = "online" | "warning" | "offline" | "unseen";

function compute(lastSeenAt: string | null): {
  status: Status;
  minutes: number | null;
} {
  if (lastSeenAt === null) return { status: "unseen", minutes: null };
  const minutes = differenceInMinutes(new Date(), new Date(lastSeenAt));
  if (minutes < 2) return { status: "online", minutes };
  if (minutes < 5) return { status: "warning", minutes };
  return { status: "offline", minutes };
}

/**
 * Status chip derived client-side from `last_seen_at` (D-14 thresholds):
 *   <2min  → green "Online"
 *   2-5min → amber "Last seen Xm ago"
 *   >5min  → red   "Offline"
 *   null   → grey  "Not yet seen"
 *
 * Status colors are semantic (per UI-SPEC color table) and intentionally
 * invariant across light/dark — meaning > theming.
 */
export function DeviceStatusChip({ lastSeenAt }: DeviceStatusChipProps) {
  const { t } = useTranslation();
  const { status, minutes } = compute(lastSeenAt);
  const classMap: Record<Status, string> = {
    online: "bg-green-100 text-green-800",
    warning: "bg-amber-100 text-amber-800",
    offline: "bg-red-100 text-red-800",
    unseen: "bg-muted text-muted-foreground",
  };
  const labelMap: Record<Status, string> = {
    online: t("signage.admin.devices.status.online"),
    warning: t("signage.admin.devices.status.warning", {
      minutes: minutes ?? 0,
    }),
    offline: t("signage.admin.devices.status.offline"),
    unseen: t("signage.admin.devices.status.unseen"),
  };
  return <Badge className={classMap[status]}>{labelMap[status]}</Badge>;
}
