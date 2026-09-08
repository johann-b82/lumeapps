/**
 * QualityInspectionCharts — three history panels (Große / Kleine / Gesamt).
 *
 * Shared granularity + Y-cap zoom cluster above the grid, one BarChart per
 * class. Bar value = Teile pro Person und Tag (a daily rate, so buckets stay
 * comparable across granularities). Tooltip surfaces the absolute quantity and
 * both denominators. Target lines follow the NULL = no line convention.
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
  Legend,
  ReferenceLine,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useSettings } from "@/hooks/useSettings";
import {
  axisProps,
  gridProps,
  tooltipCursorProps,
  tooltipStyle,
} from "@/lib/chartDefaults";
import {
  fetchInspectionsHistory,
  type BucketGranularity,
} from "@/lib/api";
import {
  deriveHrBuckets,
  formatMonthYear,
  type HrBucketGranularity,
} from "@/lib/chartTimeUtils";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";
import { qualityKeys } from "@/lib/queryKeys";

const CHART_HEIGHT = 260;

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

type ZoomLevel = { cap: number | null; label: string };

// Count-cap zoom levels — same layout as SalesActivityCard.
const COUNT_ZOOM_LEVELS: ZoomLevel[] = [
  { cap: null, label: "Auto" },
  { cap: 500, label: "500" },
  { cap: 200, label: "200" },
  { cap: 100, label: "100" },
  { cap: 50, label: "50" },
  { cap: 20, label: "20" },
  { cap: 10, label: "10" },
];

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
  if (granularity === "yearly") return m;
  const d = new Date(m);
  const day = d.getDate();
  const month = new Intl.DateTimeFormat(locale, { month: "short" }).format(d);
  return shortLocale === "de" ? `${day}. ${month}` : `${month} ${day}`;
}

type InspectionClass = "large" | "small" | "total";

/** Multi-line tooltip (§3.2). Passed as an element to <Tooltip content=…>;
 *  Recharts injects active/payload/label at render (repo pattern, see
 *  SalesActivityCard). */
function InspectionTooltip({
  active,
  payload,
  label,
  cls,
  granularity,
  locale,
  shortLocale,
  t,
}: {
  active?: boolean;
  payload?: Array<{ payload?: Record<string, string | number> }>;
  label?: string | number;
  cls: InspectionClass;
  granularity: BucketGranularity;
  locale: string;
  shortLocale: "de" | "en";
  t: (k: string) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const row = (payload[0]?.payload ?? {}) as Record<string, string | number>;
  const nf1 = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const nf0 = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
  const num = (k: string) => Number(row[`${cls}_${k}`] ?? 0);
  const line = (labelKey: string, value: string) => (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{t(labelKey)}</span>
      <span className="tabular-nums font-medium">{value}</span>
    </div>
  );
  return (
    <div style={tooltipStyle} className="rounded-md p-2 text-xs space-y-0.5">
      <div className="font-semibold mb-1">
        {formatBucketLabel(String(label), granularity, locale, shortLocale)}
      </div>
      {line("quality.inspection.tooltip.perPersonDay", nf1.format(num("per_person_day")))}
      {line("quality.inspection.tooltip.perDay", nf1.format(num("per_day")))}
      {line("quality.inspection.tooltip.qty", nf0.format(num("qty")))}
      {line("quality.inspection.tooltip.personDays", nf0.format(num("person_days")))}
      {line("quality.inspection.tooltip.inspectionDays", nf0.format(num("inspection_days")))}
      {line("quality.inspection.tooltip.inspectors", nf0.format(num("inspectors")))}
    </div>
  );
}

function InspectionPanel({
  title,
  cls,
  color,
  data,
  granularity,
  locale,
  shortLocale,
  yDomain,
  allowDataOverflow,
  target,
  targetLabel,
  t,
}: {
  title: string;
  cls: InspectionClass;
  color: string;
  data: Array<Record<string, string | number>>;
  granularity: BucketGranularity;
  locale: string;
  shortLocale: "de" | "en";
  yDomain: [number, number] | undefined;
  allowDataOverflow: boolean;
  target: number | null;
  targetLabel: string;
  t: (k: string) => string;
}) {
  return (
    <Card className="p-4">
      <p className="text-sm font-semibold mb-3">{title}</p>
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
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
            allowDecimals={false}
            width={40}
            domain={yDomain}
            allowDataOverflow={allowDataOverflow}
          />
          <Tooltip
            cursor={tooltipCursorProps}
            content={
              <InspectionTooltip
                cls={cls}
                granularity={granularity}
                locale={locale}
                shortLocale={shortLocale}
                t={t}
              />
            }
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey={`${cls}_per_person_day`} fill={color} name={title} />
          {target != null && (
            <ReferenceLine
              y={target}
              stroke="var(--color-destructive)"
              strokeDasharray="6 3"
              strokeWidth={1.5}
              ifOverflow="extendDomain"
              label={{
                value: `${targetLabel}: ${new Intl.NumberFormat(locale).format(target)}`,
                position: "insideTopRight",
                fontSize: 10,
                fill: "var(--color-destructive)",
              }}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

export function QualityInspectionCharts() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const shortLocale: "de" | "en" = i18n.language === "de" ? "de" : "en";

  const { range } = useDateRange();
  const date_from = toApiDate(range.from);
  const date_to = toApiDate(range.to);

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
  const finer = () =>
    canFiner && setGranularity(GRANULARITY_STEPS[stepIndex - 1]);
  const coarser = () =>
    canCoarser && setGranularity(GRANULARITY_STEPS[stepIndex + 1]);

  const [zoomIdx, setZoomIdx] = useState<number>(0);
  const zoom = COUNT_ZOOM_LEVELS[zoomIdx];
  const canZoomOut = zoomIdx > 0;
  const canZoomIn = zoomIdx < COUNT_ZOOM_LEVELS.length - 1;
  const yDomain: [number, number] | undefined =
    zoom.cap !== null ? [0, zoom.cap] : undefined;

  const { data: settings } = useSettings();

  const { data, isLoading } = useQuery({
    queryKey: qualityKeys.inspectionsHistory(date_from, date_to, granularity),
    queryFn: () =>
      fetchInspectionsHistory({ date_from, date_to, granularity }),
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {[1, 2, 3].map((i) => (
          <Card key={i} className="p-4">
            <div className="h-6 w-40 bg-muted rounded animate-pulse mb-3" />
            <div className="h-[260px] bg-muted rounded animate-pulse" />
          </Card>
        ))}
      </div>
    );
  }

  if (!data || data.length === 0) return null;

  const chartData = data as unknown as Array<Record<string, string | number>>;
  const granularityLabel = t(`quality.granularity.${granularity}`);

  // Target lines follow the NULL = no line convention — no baked-in default.
  // The old 150/400 defaults were unreachable for the corrected daily rate;
  // lines reappear only once Qualitätswesen configures real values.
  const targetLarge = settings?.target_inspection_large ?? null;
  const targetSmall = settings?.target_inspection_small ?? null;
  const targetTotal = settings?.target_inspection_total ?? null;
  const targetLabel = t("quality.chart.target");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-4">
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
              setZoomIdx((i) => Math.min(COUNT_ZOOM_LEVELS.length - 1, i + 1))
            }
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <InspectionPanel
          title={t("quality.inspection.large.chartTitle")}
          cls="large"
          color="#2563eb"
          data={chartData}
          granularity={granularity}
          locale={locale}
          shortLocale={shortLocale}
          yDomain={yDomain}
          allowDataOverflow={zoom.cap !== null}
          target={targetLarge}
          targetLabel={targetLabel}
          t={t}
        />
        <InspectionPanel
          title={t("quality.inspection.small.chartTitle")}
          cls="small"
          color="#0d9488"
          data={chartData}
          granularity={granularity}
          locale={locale}
          shortLocale={shortLocale}
          yDomain={yDomain}
          allowDataOverflow={zoom.cap !== null}
          target={targetSmall}
          targetLabel={targetLabel}
          t={t}
        />
        <InspectionPanel
          title={t("quality.inspection.total.chartTitle")}
          cls="total"
          color="#7c3aed"
          data={chartData}
          granularity={granularity}
          locale={locale}
          shortLocale={shortLocale}
          yDomain={yDomain}
          allowDataOverflow={zoom.cap !== null}
          target={targetTotal}
          targetLabel={targetLabel}
          t={t}
        />
      </div>
    </div>
  );
}
