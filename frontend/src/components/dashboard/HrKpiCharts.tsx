import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import { Card } from "@/components/ui/card";
import { Toggle } from "@/components/ui/toggle";
import { useSettings } from "@/hooks/useSettings";
import {
  axisProps,
  gridProps,
  tooltipCursorProps,
  tooltipItemStyle,
  tooltipLabelStyle,
  tooltipStyle,
} from "@/lib/chartDefaults";
import { fetchHrKpiHistory } from "@/lib/api";
import {
  deriveHrBuckets,
  formatMonthYear,
  yearBoundaryDates,
  type HrBucketGranularity,
} from "@/lib/chartTimeUtils";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";
import { hrKpiKeys } from "@/lib/queryKeys";

const CHART_HEIGHT = 220;

type ChartType = "area" | "bar";

interface ChartRow {
  month: string;
  below: number | null;
  above: number | null;
  value: number | null;
}

interface MiniChartProps {
  title: string;
  data: ChartRow[];
  formatValue: (v: number) => string;
  locale: string;
  shortLocale: "de" | "en";
  chartType: ChartType;
  target: number | null;
  targetLabel: string;
  granularity: HrBucketGranularity;
}

function MiniChart({ title, data, formatValue, locale, shortLocale, chartType, target, targetLabel, granularity }: MiniChartProps) {
  const hasTarget = target != null;

  // Phase 60 follow-up: x-axis labels mirror Sales RevenueChart naming.
  //   monthly   → "Apr '26"          (formatMonthYear, matches Sales)
  //   weekly    → "KW 17" / "CW 17"  (matches Sales thisMonth formatter)
  //   quarterly → "Q1 '26"           (extends Sales "Apr '26" year suffix)
  //   daily     → "15. Apr" / "Apr 15" (compact day label; not in Sales)
  const formatMonth = (m: string) => {
    if (granularity === "monthly") return formatMonthYear(m + "-01", locale);
    if (granularity === "weekly") {
      const week = m.split("-W")[1] ?? m;
      return shortLocale === "de" ? `KW ${week}` : `CW ${week}`;
    }
    if (granularity === "quarterly") {
      const [year, q] = m.split("-");
      return `${q} '${year.slice(-2)}`;
    }
    // daily: "YYYY-MM-DD" → "15. Apr" (de) / "Apr 15" (en)
    const d = new Date(m);
    const day = d.getDate();
    const month = new Intl.DateTimeFormat(locale, { month: "short" }).format(d);
    return shortLocale === "de" ? `${day}. ${month}` : `${month} ${day}`;
  };

  // Year-boundary reference lines only meaningful for monthly buckets (which
  // span multiple calendar years). For daily/weekly/quarterly this plan skips
  // boundary rendering — can be revisited in a polish pass.
  const boundaries = granularity === "monthly"
    ? yearBoundaryDates(data.map(d => d.month + "-01"))
    : [];

  const commonXAxis = (
    <XAxis
      dataKey="month"
      {...axisProps}
      tick={{ ...axisProps.tick, fontSize: 11 }}
      tickFormatter={formatMonth}
    />
  );

  const commonYAxis = (
    <YAxis
      {...axisProps}
      tick={{ ...axisProps.tick, fontSize: 11 }}
      tickFormatter={(v: number) => formatValue(v)}
      width={60}
    />
  );

  const tooltipFormatter = (v: number, name: string) => {
    // Only show the total value, hide the split segments
    if (name === "below" || name === "above") return [null, null];
    return [formatValue(v), title];
  };

  const targetLine = hasTarget ? (
    <ReferenceLine
      y={target}
      stroke="var(--color-destructive)"
      strokeDasharray="6 3"
      strokeWidth={1.5}
      label={{
        value: `${targetLabel}: ${formatValue(target)}`,
        position: "insideTopRight",
        fontSize: 10,
        fill: "var(--color-destructive)",
      }}
    />
  ) : null;

  return (
    <Card className="p-4">
      <p className="text-sm font-semibold mb-3">{title}</p>
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        {chartType === "area" ? (
          <AreaChart data={data} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
            <CartesianGrid {...gridProps} />
            {commonXAxis}
            {commonYAxis}
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={tooltipLabelStyle}
              itemStyle={tooltipItemStyle}
              cursor={tooltipCursorProps}
              labelFormatter={(label) => formatMonth(String(label))}
              formatter={
                hasTarget
                  ? (v, name) =>
                      tooltipFormatter(Number(v), String(name)) as [
                        string | null,
                        string | null,
                      ]
                  : (v) =>
                      [formatValue(Number(v)), title] as [string, string]
              }
            />
            {targetLine}
            {boundaries.map(d => (
              <ReferenceLine
                key={`yr-${d}`}
                x={d.slice(0, 7)}
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
              dataKey="value"
              stroke="var(--color-chart-current)"
              strokeWidth={2}
              fill="var(--color-chart-current)"
              fillOpacity={0.15}
              connectNulls
            />
          </AreaChart>
        ) : (
          <BarChart data={data} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
            <CartesianGrid {...gridProps} />
            {commonXAxis}
            {commonYAxis}
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={tooltipLabelStyle}
              itemStyle={tooltipItemStyle}
              cursor={tooltipCursorProps}
              labelFormatter={(label) => formatMonth(String(label))}
              formatter={
                hasTarget
                  ? (v, name) =>
                      tooltipFormatter(Number(v), String(name)) as [
                        string | null,
                        string | null,
                      ]
                  : (v) =>
                      [formatValue(Number(v)), title] as [string, string]
              }
            />
            {targetLine}
            {boundaries.map(d => (
              <ReferenceLine
                key={`yr-${d}`}
                x={d.slice(0, 7)}
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
            <Bar dataKey="value" fill="var(--color-chart-current)" />
          </BarChart>
        )}
      </ResponsiveContainer>
    </Card>
  );
}

export function HrKpiCharts() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const shortLocale: "de" | "en" = i18n.language === "de" ? "de" : "en";
  const [chartType, setChartType] = useState<ChartType>("area");
  const { data: settings } = useSettings();

  // Phase 60: consume active range from context. Server owns the bucket
  // boundaries (via _bucket_windows in Plan 01); deriveHrBuckets is used
  // client-side ONLY to pick the X-axis label formatter/granularity.
  const { range } = useDateRange();
  const date_from = toApiDate(range.from);
  const date_to = toApiDate(range.to);
  const bucketPlan = range.from && range.to
    ? deriveHrBuckets(range.from, range.to)
    : { granularity: "monthly" as const, buckets: [] };

  const { data, isLoading } = useQuery({
    queryKey: hrKpiKeys.history(date_from, date_to),
    queryFn: () => fetchHrKpiHistory({ date_from, date_to }),
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="p-4">
            <div className="h-6 w-32 bg-muted rounded animate-pulse mb-3" />
            <div className="h-[220px] bg-muted rounded animate-pulse" />
          </Card>
        ))}
      </div>
    );
  }

  if (!data?.length) return null;

  const formatPercent = (v: number) =>
    new Intl.NumberFormat(locale, {
      style: "percent",
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(v);

  const formatCurrency = (v: number) =>
    new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(v);

  const targetLabel = i18n.language === "de" ? "Soll" : "Target";

  const charts = [
    {
      key: "overtime_ratio" as const,
      title: t("hr.kpi.overtimeRatio.label"),
      format: formatPercent,
      target: settings?.target_overtime_ratio ?? null,
    },
    {
      key: "sick_leave_ratio" as const,
      title: t("hr.kpi.sickLeaveRatio.label"),
      format: formatPercent,
      target: settings?.target_sick_leave_ratio ?? null,
    },
    {
      key: "fluctuation" as const,
      title: t("hr.kpi.fluctuation.label"),
      format: formatPercent,
      target: settings?.target_fluctuation ?? null,
    },
    {
      key: "revenue_per_production_employee" as const,
      title: t("hr.kpi.revenuePerProductionEmployee.label"),
      format: formatCurrency,
      target: settings?.target_revenue_per_employee ?? null,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Toggle<ChartType>
          segments={[
            { value: "bar", label: t("dashboard.chart.type.bar") },
            { value: "area", label: t("hr.chart.type.area") },
          ] as const}
          value={chartType}
          onChange={setChartType}
          aria-label="Chart type"
          variant="muted"
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {charts.map((chart) => {
          const chartData: ChartRow[] = data.map((p) => {
            const val = p[chart.key];
            if (chart.target == null || val == null) {
              return { month: p.month, value: val, below: null, above: null };
            }
            return {
              month: p.month,
              value: val,
              below: Math.min(val, chart.target),
              above: val > chart.target ? val - chart.target : 0,
            };
          });

          return (
            <MiniChart
              key={chart.key}
              title={chart.title}
              data={chartData}
              formatValue={chart.format}
              locale={locale}
              shortLocale={shortLocale}
              chartType={chartType}
              target={chart.target}
              targetLabel={targetLabel}
              granularity={bucketPlan.granularity}
            />
          );
        })}
      </div>
    </div>
  );
}
