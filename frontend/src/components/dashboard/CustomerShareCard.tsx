import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, ChevronUp } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  useCustomerShare,
  type CustomerShareEntry,
  type CustomerShareSource,
} from "@/hooks/useCustomerShare";

interface Props {
  startDate?: string;
  endDate?: string;
  source: CustomerShareSource;
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

export function CustomerShareCard({
  startDate,
  endDate,
  source,
  className,
}: Props) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "de-DE";
  const q = useCustomerShare(source, startDate ?? "", endDate ?? "", 14);
  // Default = Top-3 only. Toggle reveals positions 4-14.
  const [expanded, setExpanded] = useState(false);

  const formatCurrency = (n: number) =>
    new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(n);

  const data = q.data;
  const titleKey =
    source === "auftraege"
      ? "sales.customer_share.title_auftraege"
      : "sales.customer_share.title_revenues";

  return (
    <Card className={`p-6 h-full flex flex-col ${className ?? ""}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {t(titleKey)}
      </p>
      {q.isLoading ? (
        <div className="mt-4 h-48 w-full bg-muted animate-pulse" />
      ) : (() => {
        const allCustomers: CustomerShareEntry[] = data?.top_customers ?? [];
        const totalAll = data?.total_value ?? 0;
        if (totalAll <= 0 || allCustomers.length === 0) {
          return (
            <p className="mt-4 text-sm text-muted-foreground italic">
              {t("sales.customer_share.empty")}
            </p>
          );
        }

        // Always at most 14 customers (backend cap). Default view: Top-3.
        const visible = expanded ? allCustomers : allCustomers.slice(0, 3);
        const visibleSum = visible.reduce((s, c) => s + c.total_value, 0);
        const remainingValue = Math.max(0, totalAll - visibleSum);

        const baseColors = [
          "var(--primary)",
          "var(--color-chart-3, #f59e0b)",
          "var(--color-chart-2, #10b981)",
        ];
        const segments: WaterfallSegment[] = visible.map((c, i) => ({
          label: c.name,
          short: `${i + 1}. ${c.name}`,
          value: c.total_value,
          pct: c.share_pct,
          // Cycle through the 3 base colors for visual rhythm.
          color: baseColors[i % baseColors.length],
        }));
        if (remainingValue > 0) {
          segments.push({
            label: t("sales.customer_share.remaining"),
            short: t("sales.customer_share.remaining"),
            value: remainingValue,
            pct: (remainingValue / totalAll) * 100,
            color: "var(--muted)",
          });
        }

        const canToggle = allCustomers.length > 3;
        return (
          <>
            <Waterfall segments={segments} formatCurrency={formatCurrency} />
            {canToggle && (
              <div className="mt-3 flex justify-center">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 gap-1.5 text-xs"
                  aria-label={t(
                    expanded
                      ? "sales.customer_share.collapse_aria"
                      : "sales.customer_share.expand_aria",
                  )}
                  onClick={() => setExpanded((v) => !v)}
                >
                  {expanded ? (
                    <>
                      <ChevronUp className="h-3.5 w-3.5" />
                      {t("sales.customer_share.collapse_label")}
                    </>
                  ) : (
                    <>
                      <ChevronDown className="h-3.5 w-3.5" />
                      {t("sales.customer_share.expand_label", {
                        count: Math.min(allCustomers.length - 3, 11),
                      })}
                    </>
                  )}
                </Button>
              </div>
            )}
          </>
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
  // Horizontal waterfall: each row's floating bar starts where the
  // previous ended. The "Restkunden" row pads cumulative to 100 %.
  const rowCount = segments.length;
  const rowH = 26;
  const rowGap = 6;
  const padL = 240;
  const padR = 60;
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
          <g key={`${r.rowIdx}-${r.seg.label}`}>
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
