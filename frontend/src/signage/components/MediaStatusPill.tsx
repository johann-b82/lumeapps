import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { signageKeys } from "@/lib/queryKeys";
import { signageApi } from "@/signage/lib/signageApi";
import { Badge } from "@/components/ui/badge";
import type { SignageConversionStatus } from "@/signage/lib/signageTypes";

export interface MediaStatusPillProps {
  mediaId: string;
  initialStatus?: SignageConversionStatus | null;
  initialError?: string | null;
}

/**
 * Live PPTX conversion status pill. Polls /api/signage/media/{id} every 3s
 * until the status reaches a terminal state (`done` or `failed`), then stops
 * (D-02 + Pattern 9). Renders nothing for media without a conversion status
 * (i.e. non-PPTX kinds).
 */
export function MediaStatusPill({
  mediaId,
  initialStatus,
  initialError,
}: MediaStatusPillProps) {
  const { t } = useTranslation();

  const { data } = useQuery({
    queryKey: signageKeys.mediaItem(mediaId),
    queryFn: () => signageApi.getMedia(mediaId),
    enabled: !!mediaId,
    refetchInterval: (query) => {
      const status = query.state.data?.conversion_status ?? initialStatus;
      if (
        status === "done" ||
        status === "failed" ||
        status === null ||
        status === undefined
      ) {
        return false;
      }
      return 3000;
    },
    refetchIntervalInBackground: false,
  });

  const status = data?.conversion_status ?? initialStatus ?? null;
  const errText = data?.conversion_error ?? initialError ?? null;
  if (!status) return null;

  const classMap: Record<SignageConversionStatus, string> = {
    pending: "bg-muted text-muted-foreground",
    processing: "bg-amber-100 text-amber-800 animate-pulse",
    done: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
  };
  const labelMap: Record<SignageConversionStatus, string> = {
    pending: t("signage.admin.media.status.pending"),
    processing: t("signage.admin.media.status.processing"),
    done: t("signage.admin.media.status.done"),
    failed: t("signage.admin.media.status.failed"),
  };

  return (
    <Badge
      className={classMap[status]}
      title={status === "failed" && errText ? errText : undefined}
    >
      {labelMap[status]}
    </Badge>
  );
}
