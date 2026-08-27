import { useTranslation } from "react-i18next";
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
import { fetchBelegschaftKpi, type BelegschaftKpi, type LabelWert } from "@/lib/belegschaftApi";

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

function PieKachel({
  titel,
  daten,
  farben,
  i18nPrefix,
  prozent = true,
  compact = false,
}: {
  titel: string;
  daten: LabelWert[];
  farben: Record<string, string>;
  i18nPrefix: string;
  prozent?: boolean;
  compact?: boolean;
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
      <div className={compact ? "mb-1 text-xs font-medium" : "mb-2 text-sm font-medium"}>{titel}</div>
      <ResponsiveContainer width="100%" height={compact ? 150 : 220}>
        <PieChart>
          <Pie
            data={chart}
            dataKey="value"
            nameKey="name"
            innerRadius={compact ? 28 : 40}
            outerRadius={compact ? 52 : 75}
            label={(e: { value?: number; pct?: number }) =>
              prozent ? `${e.pct ?? 0}%` : `${e.value}`
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
}: {
  data: BelegschaftKpi;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  const abteilungen = data.abteilungen.map((a) => ({ name: a.name, wert: a.wert }));
  const balkenH = compact ? 150 : 220;
  const abtH = compact
    ? Math.min(300, Math.max(140, abteilungen.length * 16))
    : Math.max(220, abteilungen.length * 22);
  const cardP = compact ? "p-2" : "p-4";
  const titelC = compact ? "mb-1 text-xs font-medium" : "mb-2 text-sm font-medium";
  return (
      <div className={compact ? "grid gap-3 md:grid-cols-2" : "grid gap-4 md:grid-cols-2"}>
        <PieKachel titel={t("belegschaft.geschlecht")} daten={data.geschlecht} farben={GESCHLECHT_FARBEN} i18nPrefix="belegschaft.g" compact={compact} />
        <PieKachel titel={t("belegschaft.beschaeftigung")} daten={data.beschaeftigung} farben={BESCH_FARBEN} i18nPrefix="belegschaft.b" prozent={false} compact={compact} />

        {/* Neu vs. Bestand: absolute Zahlen (Balken), kein Prozent. */}
        <Card className={cardP}>
          <div className={titelC}>{t("belegschaft.eintritt")}</div>
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

        <Card className={cardP}>
          <div className={titelC}>{t("belegschaft.abteilungen")}</div>
          <ResponsiveContainer width="100%" height={abtH}>
            <BarChart data={abteilungen} layout="vertical" margin={{ top: 4, right: 32, left: 8, bottom: 4 }}>
              <CartesianGrid {...gridProps} horizontal={false} />
              <XAxis type="number" {...axisProps} allowDecimals={false} />
              <YAxis
                type="category"
                dataKey="name"
                {...axisProps}
                tick={compact ? { fill: "var(--color-muted-foreground)", fontSize: 9 } : axisProps.tick}
                width={compact ? 116 : 150}
                interval={0}
              />
              <Tooltip cursor={tooltipCursorProps} contentStyle={tooltipStyle} itemStyle={tooltipItemStyle} labelStyle={tooltipLabelStyle} />
              <Bar
                dataKey="wert"
                radius={[0, 4, 4, 0]}
                fill="#2563eb"
                label={{ position: "right", fontSize: compact ? 10 : 11 }}
                isAnimationActive={!compact}
              />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
  );
}

export function BelegschaftKpiSection() {
  const { t } = useTranslation();
  const { data } = useQuery({ queryKey: ["hr", "belegschaft-kpi"], queryFn: fetchBelegschaftKpi });
  if (!data) return null;
  return (
    <section>
      <div className="mb-3 flex items-center gap-2">
        <Users className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <h2 className="text-base font-semibold">{t("belegschaft.title")}</h2>
        <span className="text-xs text-muted-foreground">
          {t("belegschaft.gesamt", { n: data.gesamt })}
        </span>
      </div>
      <BelegschaftKpiCharts data={data} />
    </section>
  );
}
