/**
 * ComplaintRateChart — history line/bar of the customer-complaint rate.
 *
 * One panel with the rate (%) as the primary series. Server owns
 * bucketing via _bucket_windows; this component just picks the X-axis
 * label formatter from the active date range (same helper as the audit
 * chart).
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
} from "recharts";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  axisProps,
  gridProps,
  tooltipCursorProps,
  tooltipItemStyle,
  tooltipLabelStyle,
  tooltipStyle,
} from "@/lib/chartDefaults";
import {
  fetchComplaintRateHistory,
  type BucketGranularity,
  type ComplaintType,
  type QtyMode,
} from "@/lib/api";
import {
  deriveHrBuckets,
  formatMonthYear,
  type HrBucketGranularity,
} from "@/lib/chartTimeUtils";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";
import { qualityKeys } from "@/lib/queryKeys";

const CHART_HEIGHT = 280;

interface ComplaintRateChartProps {
  qtyMode: QtyMode;
  complaintType: ComplaintType;
}

// Ordered finest → coarsest. The + button moves left (finer), − right (coarser).
// Daily is excluded from the manual toggle because for a multi-month range the
// chart would render 200+ bars — the server still produces daily buckets if
// granularity is omitted and the range is short, but the toggle won't enter it.
const GRANULARITY_STEPS: BucketGranularity[] = [
  "weekly",
  "monthly",
  "quarterly",
  "yearly",
];

function mapHrToManual(g: HrBucketGranularity): BucketGranularity {
  // deriveHrBuckets returns "daily" for ranges <= 31 days; snap that to
  // "weekly" so the manual toggle never starts inside a step it can't reach.
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
  // daily fallback ("YYYY-MM-DD")
  const d = new Date(m);
  const day = d.getDate();
  const month = new Intl.DateTimeFormat(locale, { month: "short" }).format(d);
  return shortLocale === "de" ? `${day}. ${month}` : `${month} ${day}`;
}

export function ComplaintRateChart({
  qtyMode,
  complaintType,
}: ComplaintRateChartProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const shortLocale: "de" | "en" = i18n.language === "de" ? "de" : "en";

  const { range } = useDateRange();
  const date_from = toApiDate(range.from);
  const date_to = toApiDate(range.to);

  // Auto-pick the granularity that best matches the active range, then let
  // the user step finer/coarser with +/−. The auto-pick re-runs whenever
  // the range changes — preserves the "useful default on landing" behavior
  // and matches what the audit charts do today.
  const autoGranularity: BucketGranularity =
    range.from && range.to
      ? mapHrToManual(deriveHrBuckets(range.from, range.to).granularity)
      : "monthly";
  const [granularity, setGranularity] = useState<BucketGranularity>(autoGranularity);
  useEffect(() => {
    setGranularity(autoGranularity);
  }, [autoGranularity]);

  const stepIndex = GRANULARITY_STEPS.indexOf(granularity);
  const canFiner = stepIndex > 0;
  const canCoarser = stepIndex < GRANULARITY_STEPS.length - 1;
  const finer = () => canFiner && setGranularity(GRANULARITY_STEPS[stepIndex - 1]);
  const coarser = () => canCoarser && setGranularity(GRANULARITY_STEPS[stepIndex + 1]);

  const { data, isLoading } = useQuery({
    queryKey: qualityKeys.complaintRateHistory(
      date_from,
      date_to,
      qtyMode,
      complaintType,
      granularity,
    ),
    queryFn: () =>
      fetchComplaintRateHistory({
        date_from,
        date_to,
        qty_mode: qtyMode,
        complaint_type: complaintType,
        granularity,
      }),
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
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(n);

  // Recharts wants a stable shape — drop nulls to undefined so the bar is empty
  // rather than rendering a 0-height ghost bar.
  const chartData = data.map((p) => ({
    month: p.month,
    rate: p.rate ?? null,
    complaint_qty: p.complaint_qty,
    delivered_qty: p.delivered_qty,
  }));

  const granularityLabel = t(`quality.granularity.${granularity}`);

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-semibold">
          {complaintType === "internal"
            ? t("quality.complaintRate.chartTitleInternal")
            : t("quality.complaintRate.chartTitle")}
        </p>
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
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <BarChart
          data={chartData}
          margin={{ top: 4, right: 8, left: 8, bottom: 4 }}
        >
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
                ? ["—", t("quality.complaintRate.label")]
                : [formatPercent(Number(v)), t("quality.complaintRate.label")]
            }
          />
          <Bar dataKey="rate" fill="var(--color-destructive)" />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
