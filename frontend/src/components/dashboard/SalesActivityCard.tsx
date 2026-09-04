import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { KpiInfoButton } from "./KpiInfoButton";
import type { KpiInfoKey } from "@/lib/kpiInfo";
import { ZoomIn, ZoomOut } from "lucide-react";
import {
  Bar,
  BarChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useContactsWeekly } from "@/hooks/useContactsWeekly";
import { useSettings } from "@/hooks/useSettings";
import type {
  ContactsWeeklyEmployeeBucket,
  ContactsWeeklyResponse,
} from "@/hooks/useContactsWeekly";

interface Props {
  startDate?: string;
  endDate?: string;
}

// KPI mode determines how each chart pulls + renders its data:
//   "per-rep-count"  — sum int across employees (e.g. Erstkontakte)
//   "global-count"   — week-level int (e.g. Interessenten — no rep)
//   "per-rep-eur"    — sum € across employees (Angebote, Aufträge € — €-formatted)
//   "besuche-stack"  — two-segment stacked bar: visits (ORT) + onl (ONL)
type KpiMode =
  | "per-rep-count"
  | "global-count"
  | "per-rep-eur"
  | "besuche-stack";

type KpiKey =
  | "erstkontakte"
  | "interessenten"
  | "visits"
  | "angebote"
  | "orders_per_rep";

// Y-axis zoom presets — applied to every chart now (v1.56-b). Each chart
// keeps its own zoom state. Index 0 = Auto (Recharts default: scale to
// the largest weekly value). Zoom-in steps step through ever smaller
// caps. Bars exceeding the cap are clipped at the top.
type ZoomLevel = { cap: number | null; label: string };

const EUR_ZOOM_LEVELS: ZoomLevel[] = [
  { cap: null, label: "Auto" },
  { cap: 8_000_000, label: "8 Mio. €" },
  { cap: 4_000_000, label: "4 Mio. €" },
  { cap: 2_000_000, label: "2 Mio. €" },
  { cap: 1_000_000, label: "1 Mio. €" },
  { cap: 500_000, label: "500 Tsd. €" },
  { cap: 250_000, label: "250 Tsd. €" },
  { cap: 100_000, label: "100 Tsd. €" },
  { cap: 50_000, label: "50 Tsd. €" },
  { cap: 25_000, label: "25 Tsd. €" },
];

const COUNT_ZOOM_LEVELS: ZoomLevel[] = [
  { cap: null, label: "Auto" },
  { cap: 200, label: "200" },
  { cap: 100, label: "100" },
  { cap: 50, label: "50" },
  { cap: 30, label: "30" },
  { cap: 20, label: "20" },
  { cap: 10, label: "10" },
  { cap: 5, label: "5" },
];

function zoomLevelsFor(mode: KpiMode): ZoomLevel[] {
  return mode === "per-rep-eur" ? EUR_ZOOM_LEVELS : COUNT_ZOOM_LEVELS;
}

// Baked-in fallbacks used when the corresponding `target_sales_*` field
// on /api/settings is null (= "no target set"). The Vertrieb-Settings
// page lets an admin override each value per KPI.
const DEFAULT_TARGETS = {
  erstkontakte: 50,
  interessenten: 5,
  visits: 3,
  angebote: 25_000,
  orders_per_rep: 50_000,
} as const;

// `target` is the weekly team-wide goal — drives the dashed reference
// line + the "Ziel {{value}} / Woche" header label. For per-rep-eur
// charts (Angebote, Aufträge €) the value is interpreted in EUR;
// everywhere else it's a row count. ``bucketField`` is the property on
// ``ContactsWeeklyEmployeeBucket`` to read for per-rep charts.
const KPIS_BASE: {
  key: KpiKey;
  titleKey: string;
  infoKey: KpiInfoKey;
  mode: KpiMode;
  bucketField?: keyof ContactsWeeklyEmployeeBucket;
}[] = [
  { key: "erstkontakte", titleKey: "sales.kpi.erstkontakte", infoKey: "sales.erstkontakte", mode: "per-rep-count", bucketField: "erstkontakte" },
  { key: "interessenten", titleKey: "sales.kpi.interessenten", infoKey: "sales.interessenten", mode: "global-count" },
  { key: "visits", titleKey: "sales.kpi.visits", infoKey: "sales.besuche", mode: "besuche-stack" },
  { key: "angebote", titleKey: "sales.kpi.angebote", infoKey: "sales.angebote", mode: "per-rep-eur", bucketField: "angebote" },
  { key: "orders_per_rep", titleKey: "sales.kpi.orders_per_rep", infoKey: "sales.orders_per_rep", mode: "per-rep-eur", bucketField: "orders_eur" },
];

// Simple-row shape used for the non-stacked charts.
type Row = { label: string; total: number; perRep: Record<string, number> };
// Stacked-row shape for Besuche: separate ORT/ONL counts + per-rep breakdown.
type StackedRow = {
  label: string;
  ort: number;
  onl: number;
  total: number;
  perRepOrt: Record<string, number>;
  perRepOnl: Record<string, number>;
};

function buildPerRepSeries(
  data: ContactsWeeklyResponse,
  tokens: string[],
  bucketField: keyof ContactsWeeklyEmployeeBucket,
): Row[] {
  return data.weeks.map((w) => {
    const label = `KW ${String(w.iso_week).padStart(2, "0")}`;
    const rep: Record<string, number> = {};
    let total = 0;
    for (const tk of tokens) {
      const v = (w.per_employee[tk]?.[bucketField] as number | undefined) ?? 0;
      rep[tk] = v;
      total += v;
    }
    return { label, total, perRep: rep };
  });
}

function buildGlobalInteressentenSeries(data: ContactsWeeklyResponse): Row[] {
  return data.weeks.map((w) => ({
    label: `KW ${String(w.iso_week).padStart(2, "0")}`,
    total: w.interessenten ?? 0,
    perRep: {},
  }));
}

function buildBesucheStackedSeries(
  data: ContactsWeeklyResponse,
  tokens: string[],
): StackedRow[] {
  return data.weeks.map((w) => {
    const perRepOrt: Record<string, number> = {};
    const perRepOnl: Record<string, number> = {};
    let ort = 0;
    let onl = 0;
    for (const tk of tokens) {
      const e = w.per_employee[tk];
      const vOrt = e?.visits ?? 0;
      const vOnl = e?.onl ?? 0;
      perRepOrt[tk] = vOrt;
      perRepOnl[tk] = vOnl;
      ort += vOrt;
      onl += vOnl;
    }
    return {
      label: `KW ${String(w.iso_week).padStart(2, "0")}`,
      ort,
      onl,
      total: ort + onl,
      perRepOrt,
      perRepOnl,
    };
  });
}

function collectTokens(weeks: ContactsWeeklyResponse["weeks"]): string[] {
  const set = new Set<string>();
  for (const w of weeks) {
    for (const tk of Object.keys(w.per_employee)) set.add(tk);
  }
  return [...set].sort();
}

const eurFormatter = new Intl.NumberFormat("de-DE", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});
const intFormatter = new Intl.NumberFormat("de-DE");

function fmt(value: number, isCurrency: boolean): string {
  return isCurrency ? eurFormatter.format(value) : intFormatter.format(value);
}

interface TooltipPayloadItem {
  payload?: Row | StackedRow;
}

function PerRepTooltip({
  active,
  payload,
  isCurrency,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  isCurrency: boolean;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload as Row | undefined;
  if (!row || !("perRep" in row)) return null;
  const reps = Object.entries(row.perRep);
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-sm">
      <div className="mb-1 font-medium">{row.label}</div>
      <div className="mb-1 flex justify-between gap-4">
        <span className="text-muted-foreground">Gesamt</span>
        <span className="font-medium">{fmt(row.total, isCurrency)}</span>
      </div>
      {reps.map(([tk, v]) => (
        <div key={tk} className="flex justify-between gap-4">
          <span className="text-muted-foreground">{tk}</span>
          <span>{fmt(v, isCurrency)}</span>
        </div>
      ))}
    </div>
  );
}

function BesucheTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
}) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload as StackedRow | undefined;
  if (!row || !("perRepOrt" in row)) return null;
  const allTokens = Array.from(
    new Set([...Object.keys(row.perRepOrt), ...Object.keys(row.perRepOnl)]),
  ).sort();
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-sm">
      <div className="mb-1 font-medium">{row.label}</div>
      <div className="flex justify-between gap-4">
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-2 w-2 rounded-sm"
            style={{ background: "var(--primary)" }}
          />
          <span className="text-muted-foreground">Vor Ort</span>
        </span>
        <span>{intFormatter.format(row.ort)}</span>
      </div>
      <div className="flex justify-between gap-4">
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-2 w-2 rounded-sm"
            style={{ background: "var(--color-accent, #60a5fa)" }}
          />
          <span className="text-muted-foreground">Online</span>
        </span>
        <span>{intFormatter.format(row.onl)}</span>
      </div>
      <div className="mb-1 mt-1 flex justify-between gap-4 border-t border-border pt-1">
        <span className="text-muted-foreground">Gesamt</span>
        <span className="font-medium">{intFormatter.format(row.total)}</span>
      </div>
      {allTokens.length > 0 && (
        <div className="mt-1 border-t border-border pt-1">
          {allTokens.map((tk) => {
            const o = row.perRepOrt[tk] ?? 0;
            const n = row.perRepOnl[tk] ?? 0;
            if (o + n === 0) return null;
            return (
              <div key={tk} className="flex justify-between gap-4">
                <span className="text-muted-foreground">{tk}</span>
                <span>
                  {intFormatter.format(o)} + {intFormatter.format(n)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function SalesActivityCard({ startDate, endDate }: Props) {
  const { t } = useTranslation();
  const q = useContactsWeekly(startDate ?? "", endDate ?? "");
  const { data: settings } = useSettings();
  // One zoom index per chart — default 0 (Auto). Keyed by KpiKey so each
  // chart's zoom is independent.
  const [zoomIdxByKpi, setZoomIdxByKpi] = useState<Record<KpiKey, number>>({
    erstkontakte: 0,
    interessenten: 0,
    visits: 0,
    angebote: 0,
    orders_per_rep: 0,
  });
  const bumpZoom = (key: KpiKey, delta: number, max: number) => {
    setZoomIdxByKpi((prev) => ({
      ...prev,
      [key]: Math.max(0, Math.min(max, prev[key] + delta)),
    }));
  };

  // Merge admin-configured targets (fallback = baked-in defaults).
  const KPIS = useMemo(() => {
    const t1 = settings?.target_sales_erstkontakte ?? DEFAULT_TARGETS.erstkontakte;
    const t2 = settings?.target_sales_interessenten ?? DEFAULT_TARGETS.interessenten;
    const t3 = settings?.target_sales_besuche ?? DEFAULT_TARGETS.visits;
    const t4 = settings?.target_sales_angebote_eur ?? DEFAULT_TARGETS.angebote;
    const t5 =
      settings?.target_sales_orders_per_rep_eur ?? DEFAULT_TARGETS.orders_per_rep;
    return KPIS_BASE.map((k) => ({
      ...k,
      target:
        k.key === "erstkontakte"
          ? t1
          : k.key === "interessenten"
            ? t2
            : k.key === "visits"
              ? t3
              : k.key === "angebote"
                ? t4
                : t5,
    }));
  }, [settings]);

  const tokens = useMemo(
    () => (q.data ? collectTokens(q.data.weeks) : []),
    [q.data],
  );

  if (q.isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("sales.activity.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {KPIS.map((k) => (
              <div key={k.key} className="h-64 bg-muted animate-pulse rounded" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!q.data || q.data.weeks.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("sales.activity.title")}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground py-8 text-center">
          {t("sales.activity.empty")}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("sales.activity.title")}</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {KPIS.map((k) => {
          const isCurrency = k.mode === "per-rep-eur";
          const targetFormatted = isCurrency
            ? eurFormatter.format(k.target)
            : intFormatter.format(k.target);
          const targetLabel = (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <span
                className="inline-block w-3 border-t border-dashed"
                style={{ borderColor: "var(--color-destructive)" }}
              />
              {t("sales.activity.target_label", { value: targetFormatted })}
            </span>
          );
          const referenceLine = (
            <ReferenceLine
              y={k.target}
              stroke="var(--color-destructive)"
              strokeWidth={2}
              strokeDasharray="4 3"
              ifOverflow="extendDomain"
            />
          );

          // Per-chart zoom (v1.56-b: applied to every chart, not just Angebote).
          const levels = zoomLevelsFor(k.mode);
          const zoomIdx = zoomIdxByKpi[k.key];
          const zoom = levels[zoomIdx];
          const zoomControls = (
            <span className="ml-auto flex items-center gap-1">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label={t("sales.activity.zoom_out_aria")}
                disabled={zoomIdx === 0}
                onClick={() => bumpZoom(k.key, -1, levels.length - 1)}
              >
                <ZoomOut className="h-4 w-4" />
              </Button>
              <span className="text-xs text-muted-foreground min-w-[64px] text-center tabular-nums">
                {zoom.label}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label={t("sales.activity.zoom_in_aria")}
                disabled={zoomIdx === levels.length - 1}
                onClick={() => bumpZoom(k.key, +1, levels.length - 1)}
              >
                <ZoomIn className="h-4 w-4" />
              </Button>
            </span>
          );
          const yDomain: [number, number] | undefined =
            zoom.cap !== null ? [0, zoom.cap] : undefined;

          if (k.mode === "besuche-stack") {
            const data = buildBesucheStackedSeries(q.data!, tokens);
            return (
              <div key={k.key} className="flex flex-col">
                <div className="text-sm font-medium mb-2 flex items-center gap-4 flex-wrap">
                  <span className="flex items-center gap-1">
                    {t(k.titleKey)}
                    <KpiInfoButton infoKey={k.infoKey} label={t(k.titleKey)} />
                  </span>
                  {targetLabel}
                  <span className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <span
                        className="inline-block h-2 w-2 rounded-sm"
                        style={{ background: "var(--primary)" }}
                      />
                      {t("sales.kpi.visits.legend.ort")}
                    </span>
                    <span className="flex items-center gap-1">
                      <span
                        className="inline-block h-2 w-2 rounded-sm"
                        style={{ background: "var(--color-accent, #60a5fa)" }}
                      />
                      {t("sales.kpi.visits.legend.onl")}
                    </span>
                  </span>
                  {zoomControls}
                </div>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data}>
                      <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                      <YAxis
                        allowDecimals={false}
                        tick={{ fontSize: 11 }}
                        domain={yDomain}
                        allowDataOverflow={zoom.cap !== null}
                      />
                      <Tooltip
                        cursor={{ fill: "var(--color-muted)", opacity: 0.5 }}
                        content={<BesucheTooltip />}
                      />
                      <Bar
                        dataKey="ort"
                        stackId="besuche"
                        fill="var(--primary)"
                        isAnimationActive={false}
                      />
                      <Bar
                        dataKey="onl"
                        stackId="besuche"
                        fill="var(--color-accent, #60a5fa)"
                        isAnimationActive={false}
                      />
                      {referenceLine}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            );
          }

          let data: Row[];
          if (k.mode === "global-count") {
            data = buildGlobalInteressentenSeries(q.data!);
          } else {
            data = buildPerRepSeries(q.data!, tokens, k.bucketField!);
          }
          return (
            <div key={k.key} className="flex flex-col">
              <div className="text-sm font-medium mb-2 flex items-center gap-4 flex-wrap">
                <span className="flex items-center gap-1">
                  {t(k.titleKey)}
                  <KpiInfoButton infoKey={k.infoKey} label={t(k.titleKey)} />
                </span>
                {targetLabel}
                {zoomControls}
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data}>
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 11 }}
                      tickFormatter={(v: number) =>
                        isCurrency ? eurFormatter.format(v) : intFormatter.format(v)
                      }
                      width={isCurrency ? 80 : 40}
                      domain={yDomain}
                      allowDataOverflow={zoom.cap !== null}
                    />
                    <Tooltip
                      cursor={{ fill: "var(--color-muted)", opacity: 0.5 }}
                      content={<PerRepTooltip isCurrency={isCurrency} />}
                    />
                    <Bar
                      dataKey="total"
                      fill="var(--primary)"
                      isAnimationActive={false}
                      activeBar={{ fill: "var(--color-muted)" }}
                    />
                    {referenceLine}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
