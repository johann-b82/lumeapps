import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
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
//   "per-rep-eur"    — sum € across employees (Angebote, € formatted)
//   "besuche-stack"  — two-segment stacked bar: visits (ORT) + onl (ONL)
type KpiMode =
  | "per-rep-count"
  | "global-count"
  | "per-rep-eur"
  | "besuche-stack";

type KpiKey = keyof ContactsWeeklyEmployeeBucket | "interessenten";

// `target` is the weekly team-wide goal — drives the dashed reference
// line + the "Ziel {{value}} / Woche" header label. For per-rep-eur
// charts (Angebote) the value is interpreted in EUR; everywhere else
// it's a row count.
const KPIS: { key: KpiKey; titleKey: string; mode: KpiMode; target: number }[] = [
  { key: "erstkontakte", titleKey: "sales.kpi.erstkontakte", mode: "per-rep-count", target: 50 },
  { key: "interessenten", titleKey: "sales.kpi.interessenten", mode: "global-count", target: 5 },
  { key: "visits", titleKey: "sales.kpi.visits", mode: "besuche-stack", target: 3 },
  { key: "angebote", titleKey: "sales.kpi.angebote", mode: "per-rep-eur", target: 25000 },
];

// Simple-row shape used for the three non-stacked charts.
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
  kpi: "erstkontakte" | "visits" | "angebote",
): Row[] {
  return data.weeks.map((w) => {
    const label = `KW ${String(w.iso_week).padStart(2, "0")}`;
    const rep: Record<string, number> = {};
    let total = 0;
    for (const tk of tokens) {
      const v = w.per_employee[tk]?.[kpi] ?? 0;
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

// Weekly team-wide targets live on the KPIS config (above) so each chart
// renders a dashed reference line at its own goal. Hardcoded for now; if
// they ever need to be admin-configurable, move them to AppSettings to
// mirror the existing HR target_* fields.

// Y-axis zoom presets for the Angebote chart. Default index 0 = Auto
// (Recharts default behaviour: scale to the largest weekly value).
// Zoom-in steps step through ever smaller caps so small weeks become
// readable when a single mega-offer would otherwise flatten them.
// Bars exceeding the cap are clipped at the top.
const ANGEBOTE_ZOOM_LEVELS: { cap: number | null; label: string }[] = [
  { cap: null, label: "Auto" },
  { cap: 8_000_000, label: "8 Mio. €" },
  { cap: 4_000_000, label: "4 Mio. €" },
  { cap: 2_000_000, label: "2 Mio. €" },
  { cap: 1_000_000, label: "1 Mio. €" },
  { cap: 500_000, label: "500 Tsd. €" },
  { cap: 250_000, label: "250 Tsd. €" },
  { cap: 100_000, label: "100 Tsd. €" },
  { cap: 50_000, label: "50 Tsd. €" },
];

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
  // Zoom state for the Angebote Y axis — default = Auto.
  const [angeboteZoomIdx, setAngeboteZoomIdx] = useState(0);
  const angeboteZoom = ANGEBOTE_ZOOM_LEVELS[angeboteZoomIdx];

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

          if (k.mode === "besuche-stack") {
            const data = buildBesucheStackedSeries(q.data!, tokens);
            return (
              <div key={k.key} className="flex flex-col">
                <div className="text-sm font-medium mb-2 flex items-center gap-4 flex-wrap">
                  <span>{t(k.titleKey)}</span>
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
                </div>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data}>
                      <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
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
            data = buildPerRepSeries(
              q.data!,
              tokens,
              k.key as "erstkontakte" | "visits" | "angebote",
            );
          }
          return (
            <div key={k.key} className="flex flex-col">
              <div className="text-sm font-medium mb-2 flex items-center gap-4 flex-wrap">
                <span>{t(k.titleKey)}</span>
                {targetLabel}
                {k.key === "angebote" && (
                  <span className="ml-auto flex items-center gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      aria-label={t("sales.kpi.angebote.zoom_out_aria")}
                      disabled={angeboteZoomIdx === 0}
                      onClick={() =>
                        setAngeboteZoomIdx((i) => Math.max(0, i - 1))
                      }
                    >
                      <ZoomOut className="h-4 w-4" />
                    </Button>
                    <span className="text-xs text-muted-foreground min-w-[64px] text-center tabular-nums">
                      {angeboteZoom.label}
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      aria-label={t("sales.kpi.angebote.zoom_in_aria")}
                      disabled={
                        angeboteZoomIdx === ANGEBOTE_ZOOM_LEVELS.length - 1
                      }
                      onClick={() =>
                        setAngeboteZoomIdx((i) =>
                          Math.min(ANGEBOTE_ZOOM_LEVELS.length - 1, i + 1),
                        )
                      }
                    >
                      <ZoomIn className="h-4 w-4" />
                    </Button>
                  </span>
                )}
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
                      domain={
                        k.key === "angebote" && angeboteZoom.cap !== null
                          ? [0, angeboteZoom.cap]
                          : undefined
                      }
                      allowDataOverflow={
                        k.key === "angebote" && angeboteZoom.cap !== null
                      }
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
