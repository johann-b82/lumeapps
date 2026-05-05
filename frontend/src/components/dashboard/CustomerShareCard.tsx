import { useTranslation } from "react-i18next";

import { Card } from "@/components/ui/card";
import { useOrdersDistribution } from "@/hooks/useOrdersDistribution";

interface Props {
  startDate?: string;
  endDate?: string;
  className?: string;
}

interface WaterfallSegment {
  label: string;
  short: string;
  value: number;
  pct: number;
  color: string;
}

function formatPct(n: number): string {
  return `${n.toFixed(1).replace(".", ",")} %`;
}

export function CustomerShareCard({ startDate, endDate, className }: Props) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "de-DE";
  const q = useOrdersDistribution(startDate ?? "", endDate ?? "");

  const formatCurrency = (n: number) =>
    new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(n);

  const data = q.data;

  return (
    <Card className={`p-6 h-full flex flex-col ${className ?? ""}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {t("sales.orders_distribution.share_title")}
      </p>
      {q.isLoading ? (
        <div className="mt-4 h-48 w-full bg-muted animate-pulse" />
      ) : (() => {
        const top3 = data?.top3_customers ?? [];
        const top3Sum = top3.reduce((s, c) => s + c.total_value, 0);
        const totalAll =
          data && data.top3_share_pct > 0
            ? top3Sum / (data.top3_share_pct / 100)
            : 0;
        if (totalAll <= 0) {
          return (
            <p className="mt-4 text-sm text-muted-foreground italic">
              {t("sales.orders_distribution.top3_empty")}
            </p>
          );
        }
        const colors = [
          "var(--primary)",
          "var(--color-chart-3)",
          "var(--color-chart-2)",
          "var(--muted)",
        ];
        const segments: WaterfallSegment[] = top3.map((c, i) => ({
          label: c.name,
          short: `${i + 1}. ${c.name}`,
          value: c.total_value,
          pct: (c.total_value / totalAll) * 100,
          color: colors[i],
        }));
        const remainingValue = totalAll - top3Sum;
        if (remainingValue > 0) {
          segments.push({
            label: t("sales.orders_distribution.remaining"),
            short: t("sales.orders_distribution.remaining"),
            value: remainingValue,
            pct: (remainingValue / totalAll) * 100,
            color: colors[3],
          });
        }
        return (
          <Waterfall
            segments={segments}
            formatCurrency={formatCurrency}
          />
        );
      })()}
    </Card>
  );
}

function Waterfall({
  segments,
  formatCurrency,
}: {
  segments: WaterfallSegment[];
  formatCurrency: (n: number) => string;
}) {
  // Horizontal waterfall: bars stack top-to-bottom; x-axis runs 0–100%.
  // Each customer's floating bar starts where the previous one ended.
  const rowCount = segments.length;
  const rowH = 28;
  const rowGap = 8;
  const padL = 250; // left-aligned name column — sized to fit longest label
  const padR = 56;  // room for right-side pct labels
  const padT = 28;
  const padB = 12;
  const W = 720;
  const innerW = W - padL - padR;
  const H = padT + padB + rowCount * (rowH + rowGap) - rowGap;
  const xFor = (pct: number) => padL + innerW * (pct / 100);
  const yForRow = (i: number) => padT + i * (rowH + rowGap);

  let cum = 0;
  const rows = segments.map((s, i) => {
    const start = cum;
    cum += s.pct;
    return {
      seg: s,
      rowIdx: i,
      start,
      end: cum,
      xStart: xFor(start),
      xEnd: xFor(cum),
      y: yForRow(i),
    };
  });

  return (
    <div className="w-full flex-1 flex flex-col justify-between">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto"
        preserveAspectRatio="xMinYMin meet"
        role="img"
        aria-label={`Waterfall: ${segments
          .map((s) => `${s.short} ${formatPct(s.pct)}`)
          .join(", ")}`}
      >
        {/* Top axis ticks at 0/25/50/75/100 */}
        {[0, 25, 50, 75, 100].map((p) => (
          <g key={p}>
            <line
              x1={xFor(p)}
              x2={xFor(p)}
              y1={padT - 4}
              y2={H - padB}
              stroke="var(--border)"
              strokeDasharray={p === 0 || p === 100 ? undefined : "2 4"}
            />
            <text
              x={xFor(p)}
              y={padT - 8}
              fontSize="10"
              textAnchor="middle"
              fill="var(--muted-foreground)"
            >
              {p}%
            </text>
          </g>
        ))}

        {/* Connector lines between consecutive bar end-points */}
        {rows.slice(0, -1).map((r, i) => {
          const next = rows[i + 1];
          return (
            <line
              key={`c-${i}`}
              x1={r.xEnd}
              x2={r.xEnd}
              y1={r.y + rowH}
              y2={next.y}
              stroke="var(--muted-foreground)"
              strokeDasharray="3 3"
              opacity={0.6}
            />
          );
        })}
        {/* Floating segment bars + labels */}
        {rows.map((r) => (
          <g key={r.seg.label}>
            <rect
              x={r.xStart}
              y={r.y}
              width={Math.max(2, r.xEnd - r.xStart)}
              height={rowH}
              fill={r.seg.color}
              rx={3}
            />
            <text
              x={4}
              y={r.y + rowH / 2 + 4}
              fontSize="11"
              textAnchor="start"
              fill="var(--foreground)"
            >
              {`${r.seg.short} (${formatCurrency(r.seg.value)})`}
            </text>
            <text
              x={r.xEnd + 6}
              y={r.y + rowH / 2 + 4}
              fontSize="11"
              textAnchor="start"
              fontWeight="600"
              fill="var(--foreground)"
            >
              +{formatPct(r.seg.pct)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
