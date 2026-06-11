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
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
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
  fetchAuditFindingsHistory,
  type AuditTypeCode,
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

interface QualityKpiChartsProps {
  auditTypes: readonly AuditTypeCode[];
}

function formatBucketLabel(
  m: string,
  granularity: HrBucketGranularity,
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
}: {
  title: string;
  level: 1 | 2;
  data: Array<Record<string, string | number>>;
  auditTypes: readonly AuditTypeCode[];
  artLabels: Record<AuditTypeCode, string>;
  granularity: HrBucketGranularity;
  locale: string;
  shortLocale: "de" | "en";
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
  const bucketPlan =
    range.from && range.to
      ? deriveHrBuckets(range.from, range.to)
      : { granularity: "monthly" as const, buckets: [] };

  const { data, isLoading } = useQuery({
    queryKey: qualityKeys.auditFindingsHistory(date_from, date_to, auditTypes),
    queryFn: () =>
      fetchAuditFindingsHistory({
        date_from,
        date_to,
        audit_types: auditTypes,
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

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <LevelPanel
        title={t("quality.chart.level1.title")}
        level={1}
        data={chartData}
        auditTypes={auditTypes}
        artLabels={artLabels}
        granularity={bucketPlan.granularity}
        locale={locale}
        shortLocale={shortLocale}
      />
      <LevelPanel
        title={t("quality.chart.level2.title")}
        level={2}
        data={chartData}
        auditTypes={auditTypes}
        artLabels={artLabels}
        granularity={bucketPlan.granularity}
        locale={locale}
        shortLocale={shortLocale}
      />
    </div>
  );
}
