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
import { fetchBelegschaftKpi, type LabelWert } from "@/lib/belegschaftApi";

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

function PieKachel({
  titel,
  daten,
  farben,
  i18nPrefix,
}: {
  titel: string;
  daten: LabelWert[];
  farben: Record<string, string>;
  i18nPrefix: string;
}) {
  const { t } = useTranslation();
  const gesamt = daten.reduce((s, d) => s + d.wert, 0) || 1;
  const chart = daten.map((d) => ({ name: t(`${i18nPrefix}.${d.key}`, d.key), value: d.wert, key: d.key }));
  return (
    <Card className="p-4">
      <div className="mb-2 text-sm font-medium">{titel}</div>
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={chart}
            dataKey="value"
            nameKey="name"
            innerRadius={40}
            outerRadius={75}
            label={(e: { value?: number }) =>
              `${e.value} · ${Math.round(((e.value ?? 0) / gesamt) * 100)}%`
            }
            labelLine={false}
          >
            {chart.map((d) => (
              <Cell key={d.key} fill={farben[d.key] ?? "#94a3b8"} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} itemStyle={tooltipItemStyle} labelStyle={tooltipLabelStyle} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </Card>
  );
}

export function BelegschaftKpiSection() {
  const { t } = useTranslation();
  const { data } = useQuery({ queryKey: ["hr", "belegschaft-kpi"], queryFn: fetchBelegschaftKpi });
  if (!data) return null;

  const abteilungen = data.abteilungen.map((a) => ({ name: a.name, wert: a.wert }));

  return (
    <section>
      <div className="mb-3 flex items-center gap-2">
        <Users className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <h2 className="text-base font-semibold">{t("belegschaft.title")}</h2>
        <span className="text-xs text-muted-foreground">
          {t("belegschaft.gesamt", { n: data.gesamt })}
        </span>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <PieKachel titel={t("belegschaft.geschlecht")} daten={data.geschlecht} farben={GESCHLECHT_FARBEN} i18nPrefix="belegschaft.g" />
        <PieKachel titel={t("belegschaft.beschaeftigung")} daten={data.beschaeftigung} farben={BESCH_FARBEN} i18nPrefix="belegschaft.b" />

        {/* Neu vs. Bestand: absolute Zahlen (Balken), kein Prozent. */}
        <Card className="p-4">
          <div className="mb-2 text-sm font-medium">{t("belegschaft.eintritt")}</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={data.eintritt.map((d) => ({ name: t(`belegschaft.e.${d.key}`, d.key), wert: d.wert, key: d.key }))}
              margin={{ top: 24, right: 8, left: 8, bottom: 4 }}
            >
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="name" {...axisProps} />
              <YAxis {...axisProps} allowDecimals={false} />
              <Tooltip cursor={tooltipCursorProps} contentStyle={tooltipStyle} itemStyle={tooltipItemStyle} labelStyle={tooltipLabelStyle} />
              <Bar dataKey="wert" radius={[4, 4, 0, 0]} label={{ position: "top", fontSize: 12 }}>
                {data.eintritt.map((d) => (
                  <Cell key={d.key} fill={EINTRITT_FARBEN[d.key] ?? "#94a3b8"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-4">
          <div className="mb-2 text-sm font-medium">{t("belegschaft.abteilungen")}</div>
          <ResponsiveContainer width="100%" height={Math.max(220, abteilungen.length * 22)}>
            <BarChart data={abteilungen} layout="vertical" margin={{ top: 4, right: 32, left: 8, bottom: 4 }}>
              <CartesianGrid {...gridProps} horizontal={false} />
              <XAxis type="number" {...axisProps} allowDecimals={false} />
              <YAxis type="category" dataKey="name" width={130} {...axisProps} />
              <Tooltip cursor={tooltipCursorProps} contentStyle={tooltipStyle} itemStyle={tooltipItemStyle} labelStyle={tooltipLabelStyle} />
              <Bar dataKey="wert" radius={[0, 4, 4, 0]} fill="#2563eb" label={{ position: "right", fontSize: 11 }} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </section>
  );
}
