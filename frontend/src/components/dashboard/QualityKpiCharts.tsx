/**
 * QualityKpiCharts — two side-by-side history panels (Level 1 / Level 2).
 *
 * Each panel renders one stacked BarChart where the segments of each bar
 * are coloured by audit category (BH AUD / EX AUD / IN AUD / KU AUD). The
 * server provides one ``level_<n>_<ART_CODE>`` field per bucket; bars
 * pick those up directly via Recharts ``dataKey``. The audit-type filter
 * (handled on the page) drives both which fields exist in the response
 * and which segments we render — unchecking a type removes the segment.
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
  tooltipItemStyle,
  tooltipLabelStyle,
  tooltipStyle,
} from "@/lib/chartDefaults";
import {
  fetchAuditFindingsHistory,
  type AuditTypeCode,
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

// Stable colour-per-audit-type. Same palette is used in both panels so the
// reader's legend mapping carries between the Level 1 and Level 2 charts.
// Picked from Tailwind v3 named hues; deliberately NOT --color-destructive
// (that one is reserved for "above target" lines).
const ART_COLOR: Record<AuditTypeCode, string> = {
  "BH AUD": "#2563eb", // blue-600   — regulatory
  "EX AUD": "#7c3aed", // violet-600 — supplier
  "IN AUD": "#0d9488", // teal-600   — internal
  "KU AUD": "#f59e0b", // amber-500  — customer
};

// Baked-in fallbacks used when the corresponding target field on
// /api/settings is null. The /settings/quality page lets an admin
// override either value; this fallback keeps the chart honest until
// they do. Same pattern as DEFAULT_TARGETS in SalesActivityCard.
const DEFAULT_TARGETS = {
  audit_findings_level1: 0,
  audit_findings_level2: 5,
  complaint_rate_customer: 0.02,
  complaint_rate_internal: 0.04,
} as const;

const GRANULARITY_STEPS: BucketGranularity[] = [
  "weekly",
  "monthly",
  "quarterly",
  "yearly",
];

// Y-axis zoom presets for finding counts — same SalesActivity pattern.
type ZoomLevel = { cap: number | null; label: string };

const COUNT_ZOOM_LEVELS: ZoomLevel[] = [
  { cap: null, label: "Auto" },
  { cap: 100, label: "100" },
  { cap: 50, label: "50" },
  { cap: 20, label: "20" },
  { cap: 10, label: "10" },
  { cap: 5, label: "5" },
  { cap: 3, label: "3" },
  { cap: 1, label: "1" },
];

function mapHrToManual(g: HrBucketGranularity): BucketGranularity {
  // deriveHrBuckets returns "daily" for ranges <= 31 days; snap that to
  // "weekly" so the manual toggle never starts inside a step it can't reach.
  if (g === "daily") return "weekly";
  return g;
}

interface QualityKpiChartsProps {
  auditTypes: readonly AuditTypeCode[];
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

// One self-contained panel — Level 1 or Level 2.
function LevelPanel({
  title,
  level,
  data,
  auditTypes,
  artLabels,
  granularity,
  locale,
  shortLocale,
  target,
  targetLabel,
  yDomain,
  allowDataOverflow,
}: {
  title: string;
  level: 1 | 2;
  data: Array<Record<string, string | number>>;
  auditTypes: readonly AuditTypeCode[];
  artLabels: Record<AuditTypeCode, string>;
  granularity: BucketGranularity;
  locale: string;
  shortLocale: "de" | "en";
  target: number | null;
  targetLabel: string;
  yDomain: [number, number] | undefined;
  allowDataOverflow: boolean;
}) {
  return (
    <Card className="p-4">
      <p className="text-sm font-semibold mb-3">{title}</p>
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <BarChart
          data={data}
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
            allowDecimals={false}
            width={40}
            domain={yDomain}
            allowDataOverflow={allowDataOverflow}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            labelStyle={tooltipLabelStyle}
            itemStyle={tooltipItemStyle}
            cursor={tooltipCursorProps}
            labelFormatter={(label) =>
              formatBucketLabel(String(label), granularity, locale, shortLocale)
            }
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {auditTypes.map((code) => (
            <Bar
              key={code}
              dataKey={`level_${level}_${code.replace(/\s+/g, "_")}`}
              name={artLabels[code]}
              fill={ART_COLOR[code]}
              stackId="findings"
            />
          ))}
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

export function QualityKpiCharts({ auditTypes }: QualityKpiChartsProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const shortLocale: "de" | "en" = i18n.language === "de" ? "de" : "en";

  const { range } = useDateRange();
  const date_from = toApiDate(range.from);
  const date_to = toApiDate(range.to);

  // Auto-pick granularity from the active range, then let the user step
  // finer/coarser with the +/− cluster. Re-runs whenever the range changes
  // — preserves the "useful default on landing" behavior.
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

  // Y-axis zoom — Sales-Activity pattern. Index 0 = Auto.
  const [zoomIdx, setZoomIdx] = useState<number>(0);
  const zoom = COUNT_ZOOM_LEVELS[zoomIdx];
  const canZoomOut = zoomIdx > 0;
  const canZoomIn = zoomIdx < COUNT_ZOOM_LEVELS.length - 1;
  const yDomain: [number, number] | undefined =
    zoom.cap !== null ? [0, zoom.cap] : undefined;

  // Per-level thresholds. NULL on the settings record falls through to
  // the baked-in DEFAULT_TARGETS so the chart always shows a reference
  // line until the admin explicitly clears it.
  const { data: settings } = useSettings();
  const targetLevel1 =
    settings?.target_audit_findings_level1 ?? DEFAULT_TARGETS.audit_findings_level1;
  const targetLevel2 =
    settings?.target_audit_findings_level2 ?? DEFAULT_TARGETS.audit_findings_level2;
  const targetLabel = t("quality.chart.target");

  const { data, isLoading } = useQuery({
    queryKey: qualityKeys.auditFindingsHistory(
      date_from,
      date_to,
      auditTypes,
      granularity,
    ),
    queryFn: () =>
      fetchAuditFindingsHistory({
        date_from,
        date_to,
        audit_types: auditTypes,
        granularity,
      }),
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {[1, 2].map((i) => (
          <Card key={i} className="p-4">
            <div className="h-6 w-40 bg-muted rounded animate-pulse mb-3" />
            <div className="h-[260px] bg-muted rounded animate-pulse" />
          </Card>
        ))}
      </div>
    );
  }

  if (!data || data.length === 0) return null;

  // Recharts wants flat numeric props per row. The API already provides
  // exactly that shape — pass it through unchanged.
  const chartData = data as unknown as Array<Record<string, string | number>>;

  const artLabels: Record<AuditTypeCode, string> = {
    "BH AUD": t("quality.auditType.BH_AUD"),
    "EX AUD": t("quality.auditType.EX_AUD"),
    "IN AUD": t("quality.auditType.IN_AUD"),
    "KU AUD": t("quality.auditType.KU_AUD"),
  };

  const granularityLabel = t(`quality.granularity.${granularity}`);

  return (
    <div className="space-y-4">
      {/* Single toggle row shared by both panels — Granularity (Woche /
          Monat / Quartal / Jahr) and Y-axis Zoom (SalesActivity pattern). */}
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
              setZoomIdx((i) =>
                Math.min(COUNT_ZOOM_LEVELS.length - 1, i + 1),
              )
            }
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <LevelPanel
          title={t("quality.chart.level1.title")}
          level={1}
          data={chartData}
          auditTypes={auditTypes}
          artLabels={artLabels}
          granularity={granularity}
          locale={locale}
          shortLocale={shortLocale}
          target={targetLevel1}
          targetLabel={targetLabel}
          yDomain={yDomain}
          allowDataOverflow={zoom.cap !== null}
        />
        <LevelPanel
          title={t("quality.chart.level2.title")}
          level={2}
          data={chartData}
          auditTypes={auditTypes}
          artLabels={artLabels}
          granularity={granularity}
          locale={locale}
          shortLocale={shortLocale}
          target={targetLevel2}
          targetLabel={targetLabel}
          yDomain={yDomain}
          allowDataOverflow={zoom.cap !== null}
        />
      </div>
    </div>
  );
}
