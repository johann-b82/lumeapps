import { useQueries, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useSettings } from "@/hooks/useSettings";
import {
  axisProps,
  gridProps,
  legendWrapperStyle,
  sensorPalette,
  tooltipCursorProps,
  tooltipItemStyle,
  tooltipLabelStyle,
  tooltipStyle,
} from "@/lib/chartDefaults";
import {
  fetchSensorReadings,
  fetchSensors,
  type SensorRead,
  type SensorReadingRead,
} from "@/lib/api";
import { sensorKeys } from "@/lib/queryKeys";
import {
  useSensorWindow,
  windowToHours,
} from "@/components/sensors/SensorTimeWindow";

type ChartRow = { ts: string } & Record<string, number | null | string>;

/**
 * SensorTimeSeriesChart — Phase 39-01. Two stacked Recharts LineCharts (°C and %)
 * with one Line per sensor. Same color index across both charts (consistent legend).
 *
 * D-07: TanStack Query refetch 15s foreground, no background, refetch on focus, 5s stale.
 * D-08 (revised v1.38 per user feedback): connectNulls={true} — bridge across
 * NULL gaps so each sensor reads as a single solid line. The previous "gaps
 * as absent segments" rendering produced isolated dots when polling missed
 * cycles, which the user reported as visually noisy.
 * D-05: sensorPalette is the only documented hex exception; no Tailwind dark variants.
 *
 * 39-02 (D-12): Render dashed destructive <ReferenceLine /> at temperature
 * and humidity thresholds when /api/settings supplies them. Null thresholds
 * collapse the line entirely (not drawn at 0).
 */
export function SensorTimeSeriesChart() {
  const { t, i18n } = useTranslation();
  const { window } = useSensorWindow();
  const hours = windowToHours(window);
  const settingsQuery = useSettings();
  const tempMin = parseThreshold(settingsQuery.data?.sensor_temperature_min);
  const tempMax = parseThreshold(settingsQuery.data?.sensor_temperature_max);
  const humMin = parseThreshold(settingsQuery.data?.sensor_humidity_min);
  const humMax = parseThreshold(settingsQuery.data?.sensor_humidity_max);

  const sensorsQuery = useQuery({
    queryKey: sensorKeys.list(),
    queryFn: fetchSensors,
    staleTime: 60_000,
  });

  const sensors = sensorsQuery.data ?? [];

  const readingResults = useQueries({
    queries: sensors.map((s) => ({
      queryKey: sensorKeys.readings(s.id, hours),
      queryFn: () => fetchSensorReadings(s.id, hours),
      refetchInterval: 15_000,
      refetchIntervalInBackground: false,
      refetchOnWindowFocus: true,
      staleTime: 5_000,
    })),
  });

  if (sensorsQuery.isError) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-destructive">
        {t("sensors.error.loading")}
      </div>
    );
  }

  const perSensor: Array<{
    sensor: SensorRead;
    readings: SensorReadingRead[];
  }> = sensors.map((s, idx) => ({
    sensor: s,
    readings: readingResults[idx]?.data ?? [],
  }));

  const chartData = buildChartData(perSensor);
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const labelFormatter = (value: unknown) => {
    const iso = typeof value === "string" ? value : String(value);
    const d = new Date(iso);
    if (!Number.isFinite(d.getTime())) return iso;
    return new Intl.DateTimeFormat(locale, {
      dateStyle: "short",
      timeStyle: "short",
    }).format(d);
  };

  const anyData = chartData.length > 0;

  return (
    <div className="space-y-8">
      <ChartCard
        title={t("sensors.chart.temperature.title")}
        empty={!anyData}
        emptyText={t("sensors.chart.empty")}
      >
        <LineChart data={chartData}>
          <CartesianGrid {...gridProps} />
          <XAxis
            dataKey="ts"
            {...axisProps}
            tickFormatter={labelFormatter}
            minTickGap={40}
          />
          <YAxis {...axisProps} />
          <Tooltip
            contentStyle={tooltipStyle}
            labelStyle={tooltipLabelStyle}
            itemStyle={tooltipItemStyle}
            cursor={tooltipCursorProps}
            labelFormatter={labelFormatter}
          />
          <Legend wrapperStyle={legendWrapperStyle} />
          {tempMin != null && (
            <ReferenceLine
              y={tempMin}
              stroke="var(--color-destructive)"
              strokeDasharray="4 4"
              label={{ value: t("sensors.threshold.min"), position: "insideTopRight", fill: "var(--color-destructive)", fontSize: 11 }}
            />
          )}
          {tempMax != null && (
            <ReferenceLine
              y={tempMax}
              stroke="var(--color-destructive)"
              strokeDasharray="4 4"
              label={{ value: t("sensors.threshold.max"), position: "insideTopRight", fill: "var(--color-destructive)", fontSize: 11 }}
            />
          )}
          {perSensor.map(({ sensor }, i) => (
            <Line
              key={sensor.id}
              type="monotone"
              dataKey={`s_${sensor.id}_temp`}
              name={sensor.name}
              stroke={sensorPalette[i % sensorPalette.length]}
              dot={false}
              connectNulls={true}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ChartCard>

      <ChartCard
        title={t("sensors.chart.humidity.title")}
        empty={!anyData}
        emptyText={t("sensors.chart.empty")}
      >
        <LineChart data={chartData}>
          <CartesianGrid {...gridProps} />
          <XAxis
            dataKey="ts"
            {...axisProps}
            tickFormatter={labelFormatter}
            minTickGap={40}
          />
          <YAxis {...axisProps} />
          <Tooltip
            contentStyle={tooltipStyle}
            labelStyle={tooltipLabelStyle}
            itemStyle={tooltipItemStyle}
            cursor={tooltipCursorProps}
            labelFormatter={labelFormatter}
          />
          <Legend wrapperStyle={legendWrapperStyle} />
          {humMin != null && (
            <ReferenceLine
              y={humMin}
              stroke="var(--color-destructive)"
              strokeDasharray="4 4"
              label={{ value: t("sensors.threshold.min"), position: "insideTopRight", fill: "var(--color-destructive)", fontSize: 11 }}
            />
          )}
          {humMax != null && (
            <ReferenceLine
              y={humMax}
              stroke="var(--color-destructive)"
              strokeDasharray="4 4"
              label={{ value: t("sensors.threshold.max"), position: "insideTopRight", fill: "var(--color-destructive)", fontSize: 11 }}
            />
          )}
          {perSensor.map(({ sensor }, i) => (
            <Line
              key={sensor.id}
              type="monotone"
              dataKey={`s_${sensor.id}_hum`}
              name={sensor.name}
              stroke={sensorPalette[i % sensorPalette.length]}
              dot={false}
              connectNulls={true}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ChartCard>
    </div>
  );
}

/**
 * Parse a Decimal-as-string threshold from /api/settings into a number.
 * Returns null for missing, null, non-finite, or unparseable values — the
 * ReferenceLine is then omitted per D-12 (never drawn at 0).
 */
function parseThreshold(raw: string | null | undefined): number | null {
  if (raw == null) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function buildChartData(
  perSensor: Array<{ sensor: SensorRead; readings: SensorReadingRead[] }>,
): ChartRow[] {
  const rows = new Map<string, ChartRow>();
  for (const { sensor, readings } of perSensor) {
    for (const r of readings) {
      const key = r.recorded_at;
      const row = rows.get(key) ?? ({ ts: key } as ChartRow);
      row[`s_${sensor.id}_temp`] =
        r.temperature != null ? Number(r.temperature) : null;
      row[`s_${sensor.id}_hum`] =
        r.humidity != null ? Number(r.humidity) : null;
      rows.set(key, row);
    }
  }
  return [...rows.values()].sort((a, b) =>
    String(a.ts).localeCompare(String(b.ts)),
  );
}

interface ChartCardProps {
  title: string;
  empty: boolean;
  emptyText: string;
  children: React.ReactElement;
}

function ChartCard({ title, empty, emptyText, children }: ChartCardProps) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <h3 className="text-sm font-medium text-foreground mb-4">{title}</h3>
      {empty ? (
        <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
          {emptyText}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          {children}
        </ResponsiveContainer>
      )}
    </div>
  );
}
