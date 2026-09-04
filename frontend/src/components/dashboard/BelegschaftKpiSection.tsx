import { useState } from "react";
import { useTranslation } from "react-i18next";
import { KpiInfoButton } from "./KpiInfoButton";
import type { KpiInfoKey } from "@/lib/kpiInfo";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { Users } from "lucide-react";
import { Card } from "@/components/ui/card";
import { axisProps, gridProps, tooltipCursorProps, tooltipItemStyle, tooltipLabelStyle, tooltipStyle } from "@/lib/chartDefaults";
import { fetchBelegschaftKpi, fetchBelegschaftMeta, type BelegschaftKpi, type LabelWert } from "@/lib/belegschaftApi";

const GESCHLECHT_FARBEN: Record<string, string> = {
  maennlich: "#3b82f6",
  weiblich: "#ec4899",
  divers: "#a78bfa",
};
const BESCH_FARBEN: Record<string, string> = {
  vollzeit: "#2563eb",
  teilzeit: "#22c55e",
  geringfuegig: "#f97316",
  extern: "#64748b",
};
const EINTRITT_FARBEN: Record<string, string> = {
  neu: "#ef4444",
  bestand: "#2563eb",
};

/** Ganzzahlige Prozente, die sich exakt zu 100 summieren (Größter-Rest-Methode). */
function prozente(werte: number[]): number[] {
  const summe = werte.reduce((a, b) => a + b, 0);
  if (summe <= 0) return werte.map(() => 0);
  const roh = werte.map((w) => (w / summe) * 100);
  const unten = roh.map((r) => Math.floor(r));
  let rest = 100 - unten.reduce((a, b) => a + b, 0);
  const nachRest = roh
    .map((r, i) => ({ i, frac: r - Math.floor(r) }))
    .sort((a, b) => b.frac - a.frac);
  const out = [...unten];
  for (let k = 0; rest > 0 && nachRest.length; k++, rest--) out[nachRest[k % nachRest.length].i] += 1;
  return out;
}

const RAD = Math.PI / 180;

/** Label MITTIG im Donut-Ring (statt außen) — nötig für die kleine (compact)
 *  Newsletter-Pie, wo außenliegende Labels oben abgeschnitten würden bzw. mit
 *  der Legende kollidieren. Weiße Schrift auf den Segmentfarben. */
function insideLabel(showPct: boolean) {
  return (p: {
    cx?: number;
    cy?: number;
    midAngle?: number;
    innerRadius?: number;
    outerRadius?: number;
    value?: number;
    pct?: number;
    payload?: { pct?: number };
  }) => {
    const cx = p.cx ?? 0;
    const cy = p.cy ?? 0;
    const mid = p.midAngle ?? 0;
    const ir = p.innerRadius ?? 0;
    const or = p.outerRadius ?? 0;
    const r = ir + (or - ir) * 0.5;
    const x = cx + r * Math.cos(-mid * RAD);
    const y = cy + r * Math.sin(-mid * RAD);
    const text = showPct ? `${p.pct ?? p.payload?.pct ?? 0}%` : `${p.value ?? ""}`;
    return (
      <text x={x} y={y} fill="#fff" fontSize={10} fontWeight={600} textAnchor="middle" dominantBaseline="central">
        {text}
      </text>
    );
  };
}

function PieKachel({
  titel,
  daten,
  farben,
  i18nPrefix,
  prozent = true,
  compact = false,
  schmal = false,
  infoKey,
}: {
  titel: string;
  infoKey?: KpiInfoKey;
  daten: LabelWert[];
  farben: Record<string, string>;
  i18nPrefix: string;
  prozent?: boolean;
  compact?: boolean;
  schmal?: boolean;
}) {
  const { t } = useTranslation();
  const pcts = prozente(daten.map((d) => d.wert));
  const chart = daten.map((d, i) => ({
    name: t(`${i18nPrefix}.${d.key}`, d.key),
    value: d.wert,
    key: d.key,
    pct: pcts[i],
  }));
  return (
    <Card className={compact ? "p-2" : "p-4"}>
      <div className={compact ? "mb-1 text-xs font-medium" : "mb-2 text-sm font-medium flex items-center gap-1"}>
        {titel}
        {!compact && infoKey && <KpiInfoButton infoKey={infoKey} label={titel} />}
      </div>
      <ResponsiveContainer width="100%" height={schmal ? 128 : compact ? 150 : 220}>
        <PieChart>
          <Pie
            data={chart}
            dataKey="value"
            nameKey="name"
            innerRadius={schmal ? 24 : compact ? 28 : 40}
            outerRadius={schmal ? 46 : compact ? 52 : 75}
            label={
              compact
                ? insideLabel(prozent)
                : (e: { value?: number; pct?: number }) => (prozent ? `${e.pct ?? 0}%` : `${e.value}`)
            }
            labelLine={false}
            // Bei kleiner (compact) Pie rendert Recharts die Zahlen-Labels mit
            // aktiver Animation nicht zuverlässig → im Newsletter Animation aus.
            isAnimationActive={!compact}
          >
            {chart.map((d) => (
              <Cell key={d.key} fill={farben[d.key] ?? "#94a3b8"} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} itemStyle={tooltipItemStyle} labelStyle={tooltipLabelStyle} />
          <Legend wrapperStyle={compact ? { fontSize: 11 } : undefined} />
        </PieChart>
      </ResponsiveContainer>
    </Card>
  );
}

/** Die vier KPI-Kacheln aus gegebenen Daten — genutzt vom Dashboard UND vom
 *  Newsletter. `compact` verkleinert Höhen/Ränder für die quadratische
 *  Newsletter-Seite; das Dashboard nutzt die normale Größe. */
export function BelegschaftKpiCharts({
  data,
  compact = false,
  schmal = false,
}: {
  data: BelegschaftKpi;
  compact?: boolean;
  /** Schmales Hochformat (Online-Buch): Donuts nebeneinander, Balken voll breit
   *  statt 2×2 — sonst wären die Spalten zu schmal fürs Abteilungs-Diagramm. */
  schmal?: boolean;
}) {
  const { t } = useTranslation();
  const abteilungenAlle = data.abteilungen.map((a) => ({ name: a.name, wert: a.wert }));
  // Compact (Newsletter, Quadrat): 16 lange Abteilungsnamen sind unlesbar →
  // größte 7 behalten, der Rest fließt in „Sonstige". Das Dashboard zeigt alle.
  let abteilungen = abteilungenAlle;
  if (compact && abteilungenAlle.length > 8) {
    const sortiert = [...abteilungenAlle].sort((a, b) => b.wert - a.wert);
    const top = sortiert.slice(0, 7);
    const restSumme = sortiert.slice(7).reduce((s, d) => s + d.wert, 0);
    const sonstIdx = top.findIndex((d) => /sonstige/i.test(d.name));
    if (sonstIdx >= 0) {
      top[sonstIdx] = { ...top[sonstIdx], wert: top[sonstIdx].wert + restSumme };
      abteilungen = top;
    } else {
      abteilungen = [...top, { name: "Sonstige", wert: restSumme }];
    }
  }
  const balkenH = schmal ? 130 : compact ? 150 : 220;
  const abtH = schmal
    ? Math.max(150, abteilungen.length * 24)
    : compact
      ? Math.max(160, abteilungen.length * 30)
      : Math.max(220, abteilungen.length * 22);
  const cardP = compact ? "p-2" : "p-4";
  const titelC = compact ? "mb-1 text-xs font-medium" : "mb-2 text-sm font-medium";
  const abtWidth = schmal ? 90 : compact ? 145 : 150;
  const abtTick =
    compact || schmal ? { fill: "var(--color-muted-foreground)", fontSize: schmal ? 8 : 9 } : axisProps.tick;

  const donutGeschlecht = (
    <PieKachel titel={t("belegschaft.geschlecht")} daten={data.geschlecht} farben={GESCHLECHT_FARBEN} i18nPrefix="belegschaft.g" compact={compact} schmal={schmal} infoKey="hr.belegschaft_geschlecht" />
  );
  const donutBesch = (
    <PieKachel titel={t("belegschaft.beschaeftigung")} daten={data.beschaeftigung} farben={BESCH_FARBEN} i18nPrefix="belegschaft.b" prozent={false} compact={compact} schmal={schmal} infoKey="hr.belegschaft_beschaeftigung" />
  );
  const cardEintritt = (
    <Card className={cardP}>
      <div className={titelC + " flex items-center gap-1"}>
        {t("belegschaft.eintritt")}
        {!compact && <KpiInfoButton infoKey="hr.belegschaft_eintritt" label={t("belegschaft.eintritt")} />}
      </div>
      <ResponsiveContainer width="100%" height={balkenH}>
        <BarChart
          data={data.eintritt.map((d) => ({ name: t(`belegschaft.e.${d.key}`, d.key), wert: d.wert, key: d.key }))}
          margin={{ top: 24, right: 8, left: 8, bottom: 4 }}
        >
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="name" {...axisProps} />
          <YAxis {...axisProps} allowDecimals={false} />
          <Tooltip cursor={tooltipCursorProps} contentStyle={tooltipStyle} itemStyle={tooltipItemStyle} labelStyle={tooltipLabelStyle} />
          <Bar dataKey="wert" radius={[4, 4, 0, 0]} label={{ position: "top", fontSize: 12 }} isAnimationActive={!compact}>
            {data.eintritt.map((d) => (
              <Cell key={d.key} fill={EINTRITT_FARBEN[d.key] ?? "#94a3b8"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
  const cardAbteilungen = (
    <Card className={cardP}>
      <div className={titelC + " flex items-center gap-1"}>
        {t("belegschaft.abteilungen")}
        {!compact && <KpiInfoButton infoKey="hr.belegschaft_abteilungen" label={t("belegschaft.abteilungen")} />}
      </div>
      <ResponsiveContainer width="100%" height={abtH}>
        <BarChart data={abteilungen} layout="vertical" margin={{ top: 4, right: 32, left: 8, bottom: 4 }}>
          <CartesianGrid {...gridProps} horizontal={false} />
          <XAxis type="number" {...axisProps} allowDecimals={false} />
          <YAxis type="category" dataKey="name" {...axisProps} tick={abtTick} width={abtWidth} interval={0} />
          <Tooltip cursor={tooltipCursorProps} contentStyle={tooltipStyle} itemStyle={tooltipItemStyle} labelStyle={tooltipLabelStyle} />
          <Bar dataKey="wert" radius={[0, 4, 4, 0]} fill="#2563eb" label={{ position: "right", fontSize: compact ? 10 : 11 }} isAnimationActive={!compact} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );

  // Newsletter (compact): festes 2×2 — auch schmal (Hochformat), damit die vier
  // KPIs auf eine Seite passen; das Abteilungs-Diagramm wird dafür schmaler
  // gesetzt (kleinere Achse). Dashboard bleibt responsiv.
  return (
    <div className={compact ? "grid grid-cols-2 gap-2" : "grid gap-4 md:grid-cols-2"}>
      {donutGeschlecht}
      {donutBesch}
      {cardEintritt}
      {cardAbteilungen}
    </div>
  );
}

export function BelegschaftKpiSection() {
  const { t } = useTranslation();
  const [jahr, setJahr] = useState<number | null>(null); // null = "Aktuell"
  const [quartal, setQuartal] = useState<number | null>(null); // null = Gesamtjahr

  const { data: meta } = useQuery({ queryKey: ["hr", "belegschaft-meta"], queryFn: fetchBelegschaftMeta });
  const { data } = useQuery({
    queryKey: ["hr", "belegschaft-kpi", jahr, quartal],
    queryFn: () => fetchBelegschaftKpi(jahr ?? undefined, quartal ?? undefined),
  });

  const jahre: number[] = meta
    ? Array.from({ length: meta.aktuelles_jahr - meta.min_jahr + 1 }, (_, i) => meta.aktuelles_jahr - i)
    : [];

  const selectCls =
    "h-8 rounded-md border border-input bg-background px-2 text-sm " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Users className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <h2 className="text-base font-semibold">{t("belegschaft.title")}</h2>
        {data && (
          <span className="text-xs text-muted-foreground">
            {data.stichtag
              ? t("belegschaft.gesamtStichtag", {
                  n: data.gesamt,
                  datum: new Date(data.stichtag).toLocaleDateString(),
                })
              : t("belegschaft.gesamt", { n: data.gesamt })}
          </span>
        )}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <select
            aria-label={t("belegschaft.jahr")}
            className={selectCls}
            value={jahr ?? ""}
            onChange={(e) => setJahr(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">{t("belegschaft.aktuell")}</option>
            {jahre.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <select
            aria-label={t("belegschaft.quartal")}
            className={selectCls}
            value={quartal ?? ""}
            disabled={jahr == null}
            onChange={(e) => setQuartal(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">{t("belegschaft.gesamtjahr")}</option>
            {[1, 2, 3, 4].map((q) => (
              <option key={q} value={q}>{`Q${q}`}</option>
            ))}
          </select>
        </div>
      </div>
      {data && <BelegschaftKpiCharts data={data} />}
    </section>
  );
}
