import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Activity } from "lucide-react";
import { runSnmpProbe, type SnmpProbeResult } from "@/lib/api";
import type { SensorDraftRow } from "@/hooks/useSensorDraft";

/**
 * Phase 40-02 — per-row Probe button (SEN-ADM-07).
 *
 * State machine: idle → running → success(inline chip 5s) / failure(toast)
 *
 * Timeout: matches the backend asyncio.wait_for(timeout=30) with a
 * client-side Promise.race(30_000) — identical sentinel pattern to
 * PollNowButton.tsx.
 *
 * Community source: uses the current draft `row.community` ONLY when
 * `row.communityDirty === true`. We never auto-fill from stored ciphertext
 * (write-only rule — backend can't decrypt anyway). For existing rows with
 * a stored community, the admin must retype it to probe. Tooltip explains.
 */

const PROBE_TIMEOUT_MS = 30_000;
const TIMEOUT_SENTINEL = "timeout";

function probeWithTimeout(
  body: Parameters<typeof runSnmpProbe>[0],
): Promise<SnmpProbeResult> {
  return Promise.race<SnmpProbeResult>([
    runSnmpProbe(body),
    new Promise<SnmpProbeResult>((_, reject) =>
      setTimeout(() => reject(new Error(TIMEOUT_SENTINEL)), PROBE_TIMEOUT_MS),
    ),
  ]);
}

type ProbeState =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "success"; result: SnmpProbeResult };

export interface SensorProbeButtonProps {
  row: SensorDraftRow;
}

export function SensorProbeButton({ row }: SensorProbeButtonProps) {
  const { t } = useTranslation();
  const [state, setState] = useState<ProbeState>({ kind: "idle" });

  // Auto-clear success chip after 5s.
  useEffect(() => {
    if (state.kind !== "success") return;
    const handle = setTimeout(() => setState({ kind: "idle" }), 5000);
    return () => clearTimeout(handle);
  }, [state]);

  // Probe requires a fresh community in the draft. We cannot auto-fill
  // from stored ciphertext — the backend cannot decrypt it for the admin,
  // and the write-only rule means the field is blank on existing rows.
  const canProbe =
    row.communityDirty && row.community.length > 0 && row.host.length > 0;

  const handleClick = async () => {
    if (!canProbe) return;
    setState({ kind: "running" });
    try {
      const result = await probeWithTimeout({
        host: row.host,
        port: row.port,
        community: row.community,
        temperature_oid: row.temperature_oid || null,
        humidity_oid: row.humidity_oid || null,
        temperature_scale: row.temperature_scale,
        humidity_scale: row.humidity_scale,
      });
      setState({ kind: "success", result });
      toast.success(t("sensors.admin.probe.success"));
    } catch (err) {
      const isTimeout =
        err instanceof Error && err.message === TIMEOUT_SENTINEL;
      if (isTimeout) {
        toast.error(t("sensors.admin.probe.timeout"));
      } else {
        const detail = err instanceof Error ? err.message : "Unknown error";
        toast.error(t("sensors.admin.probe.failure", { detail }));
      }
      setState({ kind: "idle" });
    }
  };

  const label =
    state.kind === "running"
      ? t("sensors.admin.probe.running")
      : t("sensors.admin.probe.test");

  const tooltip = !canProbe ? t("sensors.admin.probe.need_community") : undefined;

  return (
    <div className="flex items-center gap-3">
      <Button
        type="button"
        variant="outline"
        onClick={handleClick}
        disabled={!canProbe || state.kind === "running"}
        title={tooltip}
        aria-busy={state.kind === "running"}
      >
        <Activity className="h-4 w-4 mr-1" aria-hidden="true" />
        {label}
      </Button>
      {state.kind === "success" && (
        <span className="inline-flex items-center rounded-md bg-primary/10 text-primary px-2 py-1 text-xs font-medium">
          {t("sensors.admin.probe.result", {
            temp: formatTemp(state.result.temperature),
            humidity: formatHumidity(state.result.humidity),
          })}
        </span>
      )}
    </div>
  );
}

function formatTemp(v: number | null): string {
  return v == null ? "—" : v.toFixed(1);
}

function formatHumidity(v: number | null): string {
  return v == null ? "—" : v.toFixed(0);
}
