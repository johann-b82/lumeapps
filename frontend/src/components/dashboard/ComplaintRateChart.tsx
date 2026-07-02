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
import { Minus, Plus, ZoomIn, ZoomOut } from "lucide-react";
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
import { useSettings } from "@/hooks/useSettings";
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

// Y-axis zoom presets — On Quality variant. Headline is now 100 % − defect,
// so "zoom in" means tightening the LOWER bound of the Y-axis (toward 100 %),
// not the upper. Each level defines [min, max] where max is always 1.0
// (= 100 %) and min steps from 0 toward 1.
type ZoomLevel = { domain: [number, number] | null; label: string };

const ON_QUALITY_ZOOM_LEVELS: ZoomLevel[] = [
  { domain: null, label: "Auto" },
  { domain: [0.90, 1.0], label: "90 %" },
  { domain: [0.95, 1.0], label: "95 %" },
  { domain: [0.98, 1.0], label: "98 %" },
  { domain: [0.99, 1.0], label: "99 %" },
  { domain: [0.995, 1.0], label: "99,5 %" },
  { domain: [0.998, 1.0], label: "99,8 %" },
  { domain: [0.999, 1.0], label: "99,9 %" },
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

  // Configurable target (from /settings/quality). Falls back to baked-in
  // defaults — same pattern as DEFAULT_TARGETS on SalesActivityCard.
  // Defects are stored as fractions (0.02 = 2 % Fehler = 98 % On Quality).
  // Supplier + subcontractor have no DB column yet; the defaults below
  // are the threshold-line that renders until the admin overrides them
  // via the (future) settings-page wiring.
  const { data: settings } = useSettings();
  const DEFAULT_COMPLAINT_TARGETS = {
    customer: 0.02,
    internal: 0.04,
    supplier: 0.02,
    subcontractor: 0.05,
  } as const;
  const target: number = (() => {
    if (complaintType === "internal") {
      return (
        settings?.target_complaint_rate_internal ??
        DEFAULT_COMPLAINT_TARGETS.internal
      );
    }
    if (complaintType === "customer") {
      return (
        settings?.target_complaint_rate_customer ??
        DEFAULT_COMPLAINT_TARGETS.customer
      );
    }
    if (complaintType === "supplier") {
      return (
        settings?.target_complaint_rate_supplier ??
        DEFAULT_COMPLAINT_TARGETS.supplier
      );
    }
    return (
      settings?.target_complaint_rate_subcontractor ??
      DEFAULT_COMPLAINT_TARGETS.subcontractor
    );
  })();

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

  // Y-axis zoom — On-Quality variant. Index 0 = Auto.
  const [zoomIdx, setZoomIdx] = useState<number>(0);
  const zoom = ON_QUALITY_ZOOM_LEVELS[zoomIdx];
  const canZoomOut = zoomIdx > 0;
  const canZoomIn = zoomIdx < ON_QUALITY_ZOOM_LEVELS.length - 1;
  const yDomain: [number, number] | undefined = zoom.domain ?? undefined;

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

  const formatOnQualityPercent = (n: number) =>
    new Intl.NumberFormat(locale, {
      style: "percent",
      minimumFractionDigits: 3,
      maximumFractionDigits: 3,
    }).format(n);

  // Map defect rate → On Quality for the bars + ref line. NULL stays
  // NULL so empty buckets render as gaps, not as zero-height ghost bars.
  const chartData = data.map((p) => ({
    month: p.month,
    on_quality: p.rate == null ? null : 1 - p.rate,
    rate: p.rate ?? null, // kept for the tooltip's "(Fehler: X%)" hint
    complaint_qty: p.complaint_qty,
    delivered_qty: p.delivered_qty,
  }));

  // Target on the settings record is stored as a defect-rate fraction
  // (e.g. 0.02 = "max 2 % Fehler"); render it as the corresponding lower
  // bound on the On-Quality axis (= 1 − target). Target is always a
  // number now (the per-type defaults guarantee it), so no null branch
  // is needed at render time.
  const onQualityTarget = 1 - target;

  const granularityLabel = t(`quality.granularity.${granularity}`);
  const onQualityLabel = t(`quality.onQuality.labelByType.${complaintType}`);

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-semibold">
          {t(`quality.onQuality.chartTitleByType.${complaintType}`)}
        </p>
        <div className="flex flex-wrap items-center gap-4">
          {/* Granularity stepper (Woche / Monat / Quartal / Jahr) */}
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
          {/* Y-axis zoom (SalesActivity pattern). ZoomOut moves toward Auto;
              ZoomIn moves toward tighter caps so small rate bars become
              readable next to a much larger target line. */}
          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              aria-label={t("quality.zoom.out")}
              title={t("quality.zoom.out")}
              disabled={!canZoomOut}
              onClick={() => setZoomIdx((i) => Math.max(0, i - 1))}
            >
              <ZoomOut className="h-4 w-4" />
            </Button>
            <span className="text-xs text-muted-foreground tabular-nums min-w-[64px] text-center">
              {zoom.label}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              aria-label={t("quality.zoom.in")}
              title={t("quality.zoom.in")}
              disabled={!canZoomIn}
              onClick={() =>
                setZoomIdx((i) =>
                  Math.min(ON_QUALITY_ZOOM_LEVELS.length - 1, i + 1),
                )
              }
            >
              <ZoomIn className="h-4 w-4" />
            </Button>
          </div>
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
            tickFormatter={(v: number) => formatOnQualityPercent(v)}
            width={70}
            domain={yDomain}
            allowDataOverflow={zoom.domain !== null}
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
                ? ["—", onQualityLabel]
                : [formatOnQualityPercent(Number(v)), onQualityLabel]
            }
          />
          <ReferenceLine
            y={onQualityTarget}
            stroke="var(--color-destructive)"
            strokeDasharray="6 3"
            strokeWidth={1.5}
            // ifOverflow=extendDomain keeps the threshold visible when
            // the data sits far above (or far below) the target — same
            // trick the SalesActivityCard uses for its target lines.
            ifOverflow="extendDomain"
            label={{
              value: t("quality.onQuality.minTarget", {
                value: formatOnQualityPercent(onQualityTarget),
              }),
              position: "insideBottomRight",
              fontSize: 10,
              fill: "var(--color-destructive)",
            }}
          />
          <Bar dataKey="on_quality" fill="var(--color-chart-current)" />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
