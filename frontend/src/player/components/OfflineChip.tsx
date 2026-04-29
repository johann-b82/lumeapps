// Phase 47 UI-SPEC §Offline indicator chip: amber bottom-right pill.
// Visibility rules (UI-SPEC §"Visibility rules"):
//   show iff sidecarStatus === 'offline'.
//   ('unknown' and 'online' both hide the chip — defaults to assumed-OK.)

import { WifiOff } from "lucide-react";
import { t } from "@/player/lib/strings";
import type { SidecarStatus } from "@/player/hooks/useSidecarStatus";

export interface OfflineChipProps {
  sidecarStatus: SidecarStatus;
}

export function OfflineChip({ sidecarStatus }: OfflineChipProps) {
  if (sidecarStatus !== "offline") return null;
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={t("offline.aria_label")}
      className="fixed bottom-8 right-8 z-50 px-3 py-2 rounded-full bg-neutral-900/80 backdrop-blur-sm border border-neutral-700 flex items-center gap-1 text-sm font-semibold text-amber-400"
    >
      <WifiOff className="w-4 h-4" aria-hidden="true" />
      <span>{t("offline.label")}</span>
    </div>
  );
}
