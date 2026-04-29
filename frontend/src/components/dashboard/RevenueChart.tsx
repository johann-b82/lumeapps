import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  ResponsiveContainer,
  BarChart,
  AreaChart,
  Area,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from "recharts";
import { Card } from "@/components/ui/card";
import { Toggle } from "@/components/ui/toggle";
import {
  axisProps,
  gridProps,
  legendWrapperStyle,
  tooltipCursorProps,
  tooltipItemStyle,
  tooltipLabelStyle,
  tooltipStyle,
} from "@/lib/chartDefaults";
import { fetchChartData } from "@/lib/api";
import { buildMonthSpine, mergeIntoSpine, formatMonthYear, yearBoundaryDates } from "@/lib/chartTimeUtils";
import { kpiKeys } from "@/lib/queryKeys";
import { selectComparisonMode } from "@/lib/chartComparisonMode";
import { computePrevBounds } from "@/lib/prevBounds";
import { formatChartSeriesLabel } from "@/lib/periodLabels";
import type { Preset } from "@/lib/dateUtils";
import type { DateRangeValue } from "@/components/dashboard/DateRangeFilter";

interface RevenueChartProps {
  startDate?: string;
  endDate?: string;
  preset: Preset;
  range: DateRangeValue;
}

type ChartType = "bar" | "area";

const GRANULARITY = "monthly" as const;
const CHART_TYPES = ["bar", "area"] as const satisfies readonly [ChartType, ChartType];

export function RevenueChart({
  startDate,
  endDate,
  preset,
  range,
}: RevenueChartProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const i18nLocale: "de" | "en" = i18n.language === "de" ? "de" : "en";
  const [chartType, setChartType] = useState<ChartType>("bar");

  // Phase 10: derive comparison mode + prev bounds before the query so
  // both inputs flow into the cache key (SC5 lock-step with KPI cards).
  const mode = selectComparisonMode(preset);
  const prevBounds = computePrevBounds(preset, range);
  const prevStart =
    mode === "previous_period"
      ? prevBounds.prev_period_start
      : mode === "previous_year"
        ? prevBounds.prev_year_start
        : undefined;
  const prevEnd =
    mode === "previous_period"
      ? prevBounds.prev_period_end
      : mode === "previous_year"
        ? prevBounds.prev_year_end
        : undefined;

  const { data, isLoading, isError } = useQuery({
    queryKey: kpiKeys.chart(
      startDate,
      endDate,
      GRANULARITY,
      mode,
      prevStart,
      prevEnd,
    ),
    queryFn: () =>
      fetchChartData(
        startDate,
        endDate,
        GRANULARITY,
        mode,
        prevStart,
        prevEnd,
      ),
  });

  const labels = formatChartSeriesLabel(preset, range, i18nLocale, t);

  const formatCurrency = (n: number) =>
    new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(n);

  const formatXAxis = (dateStr: string) => {
    const d = new Date(dateStr);
    if (preset === "thisMonth") {
      // Show calendar week
      const jan1 = new Date(d.getFullYear(), 0, 1);
      const days = Math.floor((d.getTime() - jan1.getTime()) / 86400000);
      const cw = Math.ceil((days + jan1.getDay() + 1) / 7);
      return i18nLocale === "de" ? `KW ${cw}` : `CW ${cw}`;
    }
    // thisQuarter, thisYear, allTime → show month + year
    return formatMonthYear(dateStr, locale);
  };

  const Header = (
    <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
      <p className="text-xl font-semibold">{t("dashboard.chart.title")}</p>
      <Toggle<ChartType>
        segments={[
          { value: CHART_TYPES[0], label: t(`dashboard.chart.type.${CHART_TYPES[0]}`) },
          { value: CHART_TYPES[1], label: t(`dashboard.chart.type.${CHART_TYPES[1]}`) },
        ] as const}
        value={chartType}
        onChange={(type) => setChartType(type)}
        aria-label="Chart type"
        variant="muted"
      />
    </div>
  );

  if (isError) {
    return (
      <Card className="p-6">
        {Header}
        <p className="text-sm font-semibold">{t("dashboard.error.heading")}</p>
        <p className="text-sm text-muted-foreground">
          {t("dashboard.error.body")}
        </p>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card className="p-6">
        {Header}
        <div className="min-h-[400px] w-full bg-muted rounded animate-pulse" />
      </Card>
    );
  }

  // Phase 10: merge current + previous into a single rows array
  // keyed by positional index (Phase 8 CHART-01 alignment contract).
  // Null handling: current always numeric; prior may be null per
  // bucket (CHART-03) — Number(null) would produce a fabricated
  // zero bar/line, so we preserve null explicitly.
  const currentPoints = data?.current ?? [];
  const prevPoints = data?.previous ?? null;

  // CHART-03: gap-fill — build dense month spine for non-weekly presets
  const spine = (preset !== "thisMonth" && startDate && endDate)
    ? buildMonthSpine(startDate, endDate)
    : (preset !== "thisMonth" && currentPoints.length > 0)
      ? buildMonthSpine(currentPoints[0].date, currentPoints[currentPoints.length - 1].date)
      : null;

  const mergedCurrent = spine ? mergeIntoSpine(spine, currentPoints) : currentPoints;
  const mergedPrior = (spine && prevPoints) ? mergeIntoSpine(spine, prevPoints) : prevPoints;

  const rows = mergedCurrent.map((p, i) => {
    const priorRaw = mergedPrior ? (mergedPrior[i]?.revenue ?? null) : null;
    return {
      date: p.date,
      revenue: p.revenue === null ? null : Number(p.revenue),
      revenuePrior:
        mergedPrior === null
          ? undefined
          : priorRaw === null
            ? null
            : Number(priorRaw),
    };
  });

  const boundaries = spine ? yearBoundaryDates(spine) : [];

  const showPrior =
    mode !== "none" && data?.previous !== null && data?.previous !== undefined;

  return (
    <Card className="p-6">
      {Header}
      <div className="min-h-[400px] w-full">
        <ResponsiveContainer width="100%" height={400}>
          {chartType === "bar" ? (
            <BarChart
              data={rows}
              margin={{ top: 8, right: 16, left: 16, bottom: 8 }}
            >
              <CartesianGrid {...gridProps} />
              <XAxis
                dataKey="date"
                {...axisProps}
                tick={{ ...axisProps.tick, fontSize: 12 }}
                tickFormatter={formatXAxis}
                ticks={spine ?? undefined}
              />
              <YAxis
                {...axisProps}
                tick={{ ...axisProps.tick, fontSize: 12 }}
                tickFormatter={(v: number) => formatCurrency(v)}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                labelStyle={tooltipLabelStyle}
                itemStyle={tooltipItemStyle}
                cursor={tooltipCursorProps}
                labelFormatter={(label) => formatXAxis(String(label))}
                formatter={(v) => formatCurrency(Number(v))}
              />
              <Legend wrapperStyle={legendWrapperStyle} />
              {boundaries.map(d => (
                <ReferenceLine
                  key={d}
                  x={d}
                  stroke="var(--color-border)"
                  strokeDasharray="4 2"
                  strokeWidth={1}
                  label={{
                    value: d.slice(0, 4),
                    position: "insideTopLeft",
                    fontSize: 10,
                    fill: "var(--color-muted-foreground)",
                  }}
                />
              ))}
              <Bar
                dataKey="revenue"
                fill="var(--color-chart-current)"
                name={labels.current}
              />
              {showPrior && (
                <Bar
                  dataKey="revenuePrior"
                  fill="var(--color-chart-prior)"
                  name={labels.prior}
                />
              )}
            </BarChart>
          ) : (
            <AreaChart
              data={rows}
              margin={{ top: 8, right: 16, left: 16, bottom: 8 }}
            >
              <CartesianGrid {...gridProps} />
              <XAxis
                dataKey="date"
                {...axisProps}
                tick={{ ...axisProps.tick, fontSize: 12 }}
                tickFormatter={formatXAxis}
                ticks={spine ?? undefined}
              />
              <YAxis
                {...axisProps}
                tick={{ ...axisProps.tick, fontSize: 12 }}
                tickFormatter={(v: number) => formatCurrency(v)}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                labelStyle={tooltipLabelStyle}
                itemStyle={tooltipItemStyle}
                cursor={tooltipCursorProps}
                labelFormatter={(label) => formatXAxis(String(label))}
                formatter={(v) => formatCurrency(Number(v))}
              />
              <Legend wrapperStyle={legendWrapperStyle} />
              {boundaries.map(d => (
                <ReferenceLine
                  key={d}
                  x={d}
                  stroke="var(--color-border)"
                  strokeDasharray="4 2"
                  strokeWidth={1}
                  label={{
                    value: d.slice(0, 4),
                    position: "insideTopLeft",
                    fontSize: 10,
                    fill: "var(--color-muted-foreground)",
                  }}
                />
              ))}
              <Area
                type="monotone"
                dataKey="revenue"
                stroke="var(--color-chart-current)"
                strokeWidth={2}
                fill="var(--color-chart-current)"
                fillOpacity={0.15}
                name={labels.current}
              />
              {showPrior && (
                <Area
                  type="monotone"
                  dataKey="revenuePrior"
                  stroke="var(--color-chart-prior)"
                  strokeWidth={2}
                  fill="var(--color-chart-prior)"
                  fillOpacity={0.1}
                  name={labels.prior}
                />
              )}
            </AreaChart>
          )}
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
