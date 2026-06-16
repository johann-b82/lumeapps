/**
 * OtdChart — history bar chart of the Liefertermintreue / OTD rate.
 *
 * Mirrors ComplaintRateChart: the server owns bucketing via _bucket_windows;
 * this component picks the granularity (auto from the active range, then
 * +/− steps) and the X-axis label formatter. Bars use the primary colour —
 * a high OTD rate is good.
 */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Minus, Plus } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  axisProps,
  gridProps,
  tooltipCursorProps,
  tooltipItemStyle,
  tooltipLabelStyle,
  tooltipStyle,
} from "@/lib/chartDefaults";
import { fetchOtdHistory, type BucketGranularity } from "@/lib/api";
import {
  deriveHrBuckets,
  formatMonthYear,
  type HrBucketGranularity,
} from "@/lib/chartTimeUtils";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";
import { procurementKeys } from "@/lib/queryKeys";

const CHART_HEIGHT = 280;

// OTD target line — 98 % on-time deliveries.
const OTD_TARGET = 0.98;

const GRANULARITY_STEPS: BucketGranularity[] = [
  "weekly",
  "monthly",
  "quarterly",
  "yearly",
];

function mapHrToManual(g: HrBucketGranularity): BucketGranularity {
  if (g === "daily") return "weekly";
  return g;
}

function formatBucketLabel(
  m: string,
  granularity: BucketGranularity | HrBucketGranularity,
  locale: string,
  shortLocale: "de" | "en",
): string {
  if (granularity === "monthly") return formatMonthYear(m + "-01", locale);
  if (granularity === "weekly") {
    const week = m.split("-W")[1] ?? m;
    return shortLocale === "de" ? `KW ${week}` : `CW ${week}`;
  }
  if (granularity === "quarterly") {
    const [year, q] = m.split("-");
    return `${q} '${year.slice(-2)}`;
  }
  if (granularity === "yearly") {
    return m;
  }
  const d = new Date(m);
  const day = d.getDate();
  const month = new Intl.DateTimeFormat(locale, { month: "short" }).format(d);
  return shortLocale === "de" ? `${day}. ${month}` : `${month} ${day}`;
}

export function OtdChart() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const shortLocale: "de" | "en" = i18n.language === "de" ? "de" : "en";

  const { range, handleFilterChange } = useDateRange();
  const date_from = toApiDate(range.from);
  const date_to = toApiDate(range.to);

  // Custom von/bis entry — writes the range straight to the shared
  // DateRangeContext with the "custom" preset so cards, chart and table stay
  // in sync. parseInput keeps the date at local midnight to avoid TZ drift.
  const parseInput = (v: string) => (v ? new Date(`${v}T00:00:00`) : undefined);
  const setCustomRange = (from?: Date, to?: Date) =>
    handleFilterChange({ from, to }, "custom");

  const autoGranularity: BucketGranularity =
    range.from && range.to
      ? mapHrToManual(deriveHrBuckets(range.from, range.to).granularity)
      : "monthly";
  const [granularity, setGranularity] =
    useState<BucketGranularity>(autoGranularity);
  useEffect(() => {
    setGranularity(autoGranularity);
  }, [autoGranularity]);

  const stepIndex = GRANULARITY_STEPS.indexOf(granularity);
  const canFiner = stepIndex > 0;
  const canCoarser = stepIndex < GRANULARITY_STEPS.length - 1;
  const finer = () => canFiner && setGranularity(GRANULARITY_STEPS[stepIndex - 1]);
  const coarser = () =>
    canCoarser && setGranularity(GRANULARITY_STEPS[stepIndex + 1]);

  const { data, isLoading } = useQuery({
    queryKey: procurementKeys.otdHistory(date_from, date_to, granularity),
    queryFn: () => fetchOtdHistory({ date_from, date_to, granularity }),
  });

  if (isLoading) {
    return (
      <Card className="p-4">
        <div className="h-6 w-48 bg-muted rounded animate-pulse mb-3" />
        <div className={`h-[${CHART_HEIGHT}px] bg-muted rounded animate-pulse`} />
      </Card>
    );
  }

  if (!data || data.length === 0) return null;

  const formatPercent = (n: number) =>
    new Intl.NumberFormat(locale, {
      style: "percent",
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(n);

  const chartData = data.map((p) => ({
    month: p.month,
    rate: p.rate ?? null,
    punctual_count: p.punctual_count,
    total_count: p.total_count,
  }));

  const granularityLabel = t(`quality.granularity.${granularity}`);
  const targetLabel = `${t("procurement.otd.target")} ${formatPercent(OTD_TARGET)}`;

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <p className="text-sm font-semibold">{t("procurement.otd.chartTitle")}</p>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1">
            <Input
              type="date"
              aria-label={t("dashboard.filter.from")}
              value={date_from ?? ""}
              max={date_to ?? undefined}
              onChange={(e) => setCustomRange(parseInput(e.target.value), range.to)}
              className="h-8 w-[150px]"
            />
            <span className="text-xs text-muted-foreground">–</span>
            <Input
              type="date"
              aria-label={t("dashboard.filter.to")}
              value={date_to ?? ""}
              min={date_from ?? undefined}
              onChange={(e) => setCustomRange(range.from, parseInput(e.target.value))}
              className="h-8 w-[150px]"
            />
          </div>
          <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-7 w-7"
            onClick={coarser}
            disabled={!canCoarser}
            aria-label={t("quality.granularity.coarser")}
            title={t("quality.granularity.coarser")}
          >
            <Minus className="h-3.5 w-3.5" />
          </Button>
          <span className="text-xs text-muted-foreground tabular-nums min-w-[64px] text-center">
            {granularityLabel}
          </span>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-7 w-7"
            onClick={finer}
            disabled={!canFiner}
            aria-label={t("quality.granularity.finer")}
            title={t("quality.granularity.finer")}
          >
            <Plus className="h-3.5 w-3.5" />
          </Button>
          </div>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
          <CartesianGrid {...gridProps} />
          <XAxis
            dataKey="month"
            {...axisProps}
            tick={{ ...axisProps.tick, fontSize: 11 }}
            tickFormatter={(m) =>
              formatBucketLabel(String(m), granularity, locale, shortLocale)
            }
          />
          <YAxis
            {...axisProps}
            tick={{ ...axisProps.tick, fontSize: 11 }}
            tickFormatter={(v: number) => formatPercent(v)}
            domain={[0, 1]}
            width={60}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            labelStyle={tooltipLabelStyle}
            itemStyle={tooltipItemStyle}
            cursor={tooltipCursorProps}
            labelFormatter={(label) =>
              formatBucketLabel(String(label), granularity, locale, shortLocale)
            }
            formatter={(v) =>
              v == null
                ? ["—", t("procurement.otd.label")]
                : [formatPercent(Number(v)), t("procurement.otd.label")]
            }
          />
          <Bar dataKey="rate" fill="var(--color-primary)" />
          <ReferenceLine
            y={OTD_TARGET}
            stroke="var(--color-destructive)"
            strokeDasharray="4 4"
            label={{
              value: targetLabel,
              position: "insideTopRight",
              fontSize: 11,
              fill: "var(--color-destructive)",
            }}
          />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
