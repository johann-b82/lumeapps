import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { pollSensorsNow, type PollNowResult } from "@/lib/api";
import { sensorKeys } from "@/lib/queryKeys";

/**
 * PollNowButton — SEN-FE-07. Blocks up to 30 s while the backend runs an
 * on-demand SNMP poll. On success, invalidates every `sensorKeys.*` query so
 * cards and charts refetch within the same tick.
 *
 * D-13 — 30 s client-side Promise.race timeout mirrors the backend's
 * asyncio.wait_for(timeout=30); on timeout, we show the dedicated timeout
 * toast (not the generic failure one) so the user knows the request never
 * reached the server.
 */

const POLL_TIMEOUT_MS = 30_000;
const TIMEOUT_SENTINEL = "timeout";

function pollWithTimeout(): Promise<PollNowResult> {
  return Promise.race<PollNowResult>([
    pollSensorsNow(),
    new Promise<PollNowResult>((_, reject) =>
      setTimeout(() => reject(new Error(TIMEOUT_SENTINEL)), POLL_TIMEOUT_MS),
    ),
  ]);
}

interface PollNowButtonProps {
  size?: "default" | "sm";
}

export function PollNowButton({ size = "default" }: PollNowButtonProps = {}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: pollWithTimeout,
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: sensorKeys.all });
      toast.success(
        t("sensors.poll.success", { count: res.sensors_polled }),
      );
    },
    onError: (err: unknown) => {
      const isTimeout =
        err instanceof Error && err.message === TIMEOUT_SENTINEL;
      toast.error(
        isTimeout ? t("sensors.poll.timeout") : t("sensors.poll.failure"),
      );
    },
  });

  const Icon = mutation.isPending ? Loader2 : RefreshCw;
  const label = mutation.isPending
    ? t("sensors.poll.refreshing")
    : t("sensors.poll.now");

  return (
    <Button
      type="button"
      size={size}
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      aria-busy={mutation.isPending}
    >
      <Icon className={mutation.isPending ? "animate-spin" : undefined} />
      {label}
    </Button>
  );
}
