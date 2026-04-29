import { useQueries, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  fetchSensorReadings,
  fetchSensorStatus,
  fetchSensors,
  type SensorRead,
  type SensorReadingRead,
  type SensorStatusEntry,
} from "@/lib/api";
import { sensorKeys } from "@/lib/queryKeys";
import { useSettings } from "@/hooks/useSettings";
import { deltaClassName } from "@/components/dashboard/deltaFormat";
import { computeSensorDelta } from "@/components/sensors/sensorDelta";
import { SensorHealthChip } from "@/components/sensors/SensorHealthChip";

/**
 * SensorStatusCards — Phase 39. One KPI card per enabled sensor.
 *
 * 39-01 foundation: temperature + humidity values + freshness footer.
 * 39-02 additions:
 *   - threshold-aware text color (destructive when current value outside
 *     [min, max] from /api/settings — D-12)
 *   - DIFF-01 delta badges per value (`vs. 1h` + `vs. 24h`), computed
 *     client-side from the readings already in the query cache
 *   - DIFF-10 health chip (`/api/sensors/status`) in the card header
 *
 * D-07 refetch cadence unchanged from 39-01. The status query runs ONCE
 * at this container level (not per-card) so the N cards share a single
 * response.
 */

interface ThresholdBounds {
  min: number | null;
  max: number | null;
}

function extractBounds(
  rawMin: string | null | undefined,
  rawMax: string | null | undefined,
): ThresholdBounds {
  const min = rawMin != null ? Number(rawMin) : null;
  const max = rawMax != null ? Number(rawMax) : null;
  return {
    min: min != null && Number.isFinite(min) ? min : null,
    max: max != null && Number.isFinite(max) ? max : null,
  };
}

function isOutOfRange(value: number | null, bounds: ThresholdBounds): boolean {
  if (value == null || !Number.isFinite(value)) return false;
  if (bounds.min != null && value < bounds.min) return true;
  if (bounds.max != null && value > bounds.max) return true;
  return false;
}

export function SensorStatusCards() {
  const { t } = useTranslation();
  const settingsQuery = useSettings();

  const sensorsQuery = useQuery({
    queryKey: sensorKeys.list(),
    queryFn: fetchSensors,
    staleTime: 60_000,
  });

  const statusQuery = useQuery({
    queryKey: sensorKeys.status(),
    queryFn: fetchSensorStatus,
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    staleTime: 5_000,
  });

  const sensors = sensorsQuery.data ?? [];

  // Per-sensor readings window sized for DIFF-01 24h delta (we need at least
  // ~24.5h of history to satisfy the tolerance window around the 24h baseline).
  const DELTA_WINDOW_HOURS = 25;
  const readingResults = useQueries({
    queries: sensors.map((s) => ({
      queryKey: sensorKeys.readings(s.id, DELTA_WINDOW_HOURS),
      queryFn: () => fetchSensorReadings(s.id, DELTA_WINDOW_HOURS),
      refetchInterval: 15_000,
      refetchIntervalInBackground: false,
      refetchOnWindowFocus: true,
      staleTime: 5_000,
    })),
  });

  if (sensorsQuery.isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[0, 1, 2].map((i) => (
          <div
            key={`skel-${i}`}
            className="animate-pulse bg-muted rounded-lg h-36"
          />
        ))}
      </div>
    );
  }

  if (sensorsQuery.isError) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-destructive">
        {t("sensors.error.loading")}
      </div>
    );
  }

  const tempBounds = extractBounds(
    settingsQuery.data?.sensor_temperature_min,
    settingsQuery.data?.sensor_temperature_max,
  );
  const humBounds = extractBounds(
    settingsQuery.data?.sensor_humidity_min,
    settingsQuery.data?.sensor_humidity_max,
  );
  const statusMap = new Map<number, SensorStatusEntry>();
  for (const entry of statusQuery.data ?? []) {
    statusMap.set(entry.sensor_id, entry);
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {sensors.map((sensor, idx) => (
        <SensorCard
          key={sensor.id}
          sensor={sensor}
          readings={readingResults[idx]?.data ?? []}
          status={statusMap.get(sensor.id)}
          tempBounds={tempBounds}
          humBounds={humBounds}
        />
      ))}
    </div>
  );
}

interface SensorCardProps {
  sensor: SensorRead;
  readings: SensorReadingRead[];
  status: SensorStatusEntry | undefined;
  tempBounds: ThresholdBounds;
  humBounds: ThresholdBounds;
}

function SensorCard({
  sensor,
  readings,
  status,
  tempBounds,
  humBounds,
}: SensorCardProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de" : "en";

  // Defensive: pick the latest by max recorded_at (backend returns asc, but
  // we don't want to depend on ordering for the primary card readings).
  const latest = readings.length
    ? readings.reduce((acc, r) =>
        new Date(r.recorded_at).getTime() > new Date(acc.recorded_at).getTime()
          ? r
          : acc,
      )
    : null;

  const hasValues =
    latest != null &&
    latest.error_code == null &&
    (latest.temperature != null || latest.humidity != null);

  const tempNum =
    latest?.temperature != null ? Number(latest.temperature) : null;
  const humNum = latest?.humidity != null ? Number(latest.humidity) : null;

  const tempOut = isOutOfRange(tempNum, tempBounds);
  const humOut = isOutOfRange(humNum, humBounds);

  const tempDelta1h = computeSensorDelta(readings, "temperature", 1);
  const tempDelta24h = computeSensorDelta(readings, "temperature", 24);
  const humDelta1h = computeSensorDelta(readings, "humidity", 1);
  const humDelta24h = computeSensorDelta(readings, "humidity", 24);

  const freshnessLabel =
    latest != null
      ? (() => {
          const seconds = Math.max(
            0,
            Math.floor(
              (Date.now() - new Date(latest.recorded_at).getTime()) / 1000,
            ),
          );
          return t("sensors.kpi.freshness", { seconds });
        })()
      : t("sensors.kpi.freshness.never");

  return (
    <div className="bg-card border border-border rounded-lg p-4 space-y-4">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-medium text-foreground">{sensor.name}</h3>
        <SensorHealthChip status={status} />
      </div>

      {hasValues ? (
        <div className="flex items-start gap-6">
          <MetricBlock
            label={t("sensors.kpi.temperature")}
            value={tempNum}
            unit="°C"
            fractionDigits={1}
            outOfRange={tempOut}
            delta1h={tempDelta1h}
            delta24h={tempDelta24h}
            locale={locale}
            t={t}
          />
          <MetricBlock
            label={t("sensors.kpi.humidity")}
            value={humNum}
            unit="%"
            fractionDigits={0}
            outOfRange={humOut}
            delta1h={humDelta1h}
            delta24h={humDelta24h}
            locale={locale}
            t={t}
          />
        </div>
      ) : (
        <div className="text-sm text-muted-foreground">
          {t("sensors.empty.noReadings")}
        </div>
      )}

      <div className="text-xs text-muted-foreground pt-2 border-t border-border">
        {freshnessLabel}
      </div>
    </div>
  );
}

interface MetricBlockProps {
  label: string;
  value: number | null;
  unit: string;
  fractionDigits: number;
  outOfRange: boolean;
  delta1h: number | null;
  delta24h: number | null;
  locale: "de" | "en";
  t: (key: string, options?: Record<string, unknown>) => string;
}

function MetricBlock({
  label,
  value,
  unit,
  fractionDigits,
  outOfRange,
  delta1h,
  delta24h,
  locale,
  t,
}: MetricBlockProps) {
  const valueClass = outOfRange
    ? "text-3xl font-semibold text-destructive"
    : "text-3xl font-semibold text-foreground";
  const display =
    value != null ? `${value.toFixed(fractionDigits)} ${unit}` : "—";
  const noBaseline = t("sensors.delta.noBaseline");

  return (
    <div className="flex flex-col">
      <div className={valueClass}>{display}</div>
      <div className="text-xs text-muted-foreground mt-1">{label}</div>
      {outOfRange && (
        <div className="text-xs text-destructive mt-0.5">
          {t("sensors.threshold.outOfRange")}
        </div>
      )}
      <div className="flex flex-col gap-0.5 text-xs mt-2">
        <AbsoluteDeltaRow
          delta={delta1h}
          unit={unit}
          locale={locale}
          label={t("sensors.delta.vsHour")}
          noBaselineTooltip={noBaseline}
        />
        <AbsoluteDeltaRow
          delta={delta24h}
          unit={unit}
          locale={locale}
          label={t("sensors.delta.vsDay")}
          noBaselineTooltip={noBaseline}
        />
      </div>
    </div>
  );
}

/**
 * AbsoluteDeltaRow — mirrors the DeltaBadge color/arrow contract (CARD-02 +
 * CARD-04) but renders the raw delta in its native unit (°C, %) with one
 * decimal, instead of the percent-format used by Sales/HR dashboards.
 *
 * Reuses `deltaClassName` (same color tokens) for visual parity with the
 * rest of the app; null deltas render an em-dash with the baseline tooltip.
 */
interface AbsoluteDeltaRowProps {
  delta: number | null;
  unit: string;
  locale: "de" | "en";
  label: string;
  noBaselineTooltip: string;
}

function AbsoluteDeltaRow({
  delta,
  unit,
  locale,
  label,
  noBaselineTooltip,
}: AbsoluteDeltaRowProps) {
  const className = deltaClassName(delta);
  const text = formatAbsoluteDelta(delta, unit, locale);
  return (
    <div className="flex items-baseline gap-2">
      {delta === null ? (
        <span className={className} title={noBaselineTooltip}>
          {text}
        </span>
      ) : (
        <span className={className}>{text}</span>
      )}
      <span className="text-muted-foreground">{label}</span>
    </div>
  );
}

function formatAbsoluteDelta(
  value: number | null,
  unit: string,
  locale: "de" | "en",
): string {
  if (value === null) return "—";
  const abs = Math.abs(value);
  const fmt = new Intl.NumberFormat(locale === "de" ? "de-DE" : "en-US", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(abs);
  // Non-breaking space between number and unit (matches DE typography and
  // reads fine in EN too).
  const nbsp = "\u00A0";
  if (value > 0) return `▲ +${fmt}${nbsp}${unit}`;
  if (value < 0) return `▼ −${fmt}${nbsp}${unit}`;
  return `${fmt}${nbsp}${unit}`;
}
