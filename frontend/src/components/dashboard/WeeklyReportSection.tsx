import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { KpiInfoButton } from "./KpiInfoButton";
import type { KpiInfoKey } from "@/lib/kpiInfo";
import { toPng } from "html-to-image";
import { jsPDF } from "jspdf";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Cell,
} from "recharts";
import { CalendarRange, FileDown, Loader2, Sparkles } from "lucide-react";
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
  fetchWeeklyMeta,
  fetchWeeklyReport,
  type WeeklyPerson,
  type WochenKennzahl,
} from "@/lib/weeklyApi";

const wKeys = {
  meta: () => ["hr", "weekly", "meta"] as const,
  report: (y: number, w: number) => ["hr", "weekly", y, w] as const,
};

/** "2026-18" → { year, week, label }. */
function parseKw(s: string): { year: number; week: number } {
  const [y, w] = s.split("-");
  return { year: Number(y), week: Number(w) };
}

export function WeeklyReportSection() {
  const { t } = useTranslation();
  const reportRef = useRef<HTMLDivElement>(null);
  const [gewaehlt, setGewaehlt] = useState<string>("");
  const [aktiv, setAktiv] = useState<{ year: number; week: number } | null>(null);
  const [exportLaeuft, setExportLaeuft] = useState(false);
  const [krankEinheit, setKrankEinheit] = useState<"tage" | "std">("tage");

  const { data: meta } = useQuery({ queryKey: wKeys.meta(), queryFn: fetchWeeklyMeta });

  // Standard-KW = letzte Woche mit Daten.
  useEffect(() => {
    if (meta?.letzte_woche && !gewaehlt) setGewaehlt(meta.letzte_woche);
  }, [meta, gewaehlt]);

  const { data: report, isFetching } = useQuery({
    queryKey: aktiv ? wKeys.report(aktiv.year, aktiv.week) : ["hr", "weekly", "none"],
    queryFn: () => fetchWeeklyReport(aktiv!.year, aktiv!.week),
    enabled: aktiv != null,
  });

  const exportPdf = async () => {
    if (!reportRef.current) return;
    setExportLaeuft(true);
    try {
      const url = await toPng(reportRef.current, {
        pixelRatio: 2,
        cacheBust: true,
        // Keep the "i" buttons out of the exported image.
        filter: (node: HTMLElement) =>
          !(node instanceof HTMLElement && node.dataset.kpiInfoUi === "true"),
      });
      const img = new Image();
      img.src = url;
      await img.decode();
      const pdf = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4" });
      const pw = pdf.internal.pageSize.getWidth();
      const ph = pdf.internal.pageSize.getHeight();
      const r = Math.min((pw - 40) / img.width, (ph - 40) / img.height);
      pdf.addImage(url, "PNG", (pw - img.width * r) / 2, 20, img.width * r, img.height * r);
      pdf.save(`Weekly-Report_${report?.kw_label.replace(/\s+/g, "") ?? "KW"}.pdf`);
    } finally {
      setExportLaeuft(false);
    }
  };

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <CalendarRange className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <h2 className="text-base font-semibold">{t("weekly.title")}</h2>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <div className="inline-flex overflow-hidden rounded-md border border-input text-xs" role="group" aria-label={t("weekly.krankheitEinheit")}>
            {(["tage", "std"] as const).map((u) => (
              <button
                key={u}
                type="button"
                onClick={() => setKrankEinheit(u)}
                className={
                  "h-8 px-3 focus-visible:outline-none " +
                  (krankEinheit === u ? "bg-primary text-primary-foreground" : "bg-background hover:bg-muted")
                }
              >
                {u === "tage" ? t("weekly.einheitTage") : t("weekly.einheitStunden")}
              </button>
            ))}
          </div>
          <select
            value={gewaehlt}
            onChange={(e) => setGewaehlt(e.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2 text-sm
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {(meta?.wochen_verfuegbar ?? []).map((kw) => {
              const { year, week } = parseKw(kw);
              return (
                <option key={kw} value={kw}>
                  KW {week} / {year}
                </option>
              );
            })}
          </select>
          <button
            type="button"
            onClick={() => gewaehlt && setAktiv(parseKw(gewaehlt))}
            disabled={!gewaehlt || isFetching}
            className="inline-flex h-8 items-center gap-2 rounded-md bg-primary px-3 text-xs
                       text-primary-foreground disabled:opacity-50 focus-visible:outline-none
                       focus-visible:ring-2 focus-visible:ring-ring"
          >
            {isFetching ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            {t("weekly.erzeugen")}
          </button>
          {report && (
            <button
              type="button"
              onClick={exportPdf}
              disabled={exportLaeuft}
              className="inline-flex h-8 items-center gap-2 rounded-md border border-input px-3
                         text-xs hover:bg-muted disabled:opacity-50 focus-visible:outline-none
                         focus-visible:ring-2 focus-visible:ring-ring"
            >
              {exportLaeuft ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileDown className="h-3.5 w-3.5" />}
              {t("weekly.pdf")}
            </button>
          )}
        </div>
      </div>

      {/* Datenhinweise */}
      {meta && (
        <p className="mb-3 text-xs text-muted-foreground">
          {t("weekly.hinweisAnwesenheit", { datum: meta.anwesenheit_bis ?? "—" })}
          {!meta.hat_krankheitsdaten && " · " + t("weekly.hinweisKrank")}
        </p>
      )}

      {!report ? (
        <Card className="p-6 text-sm text-muted-foreground">{t("weekly.leer")}</Card>
      ) : (
        <div ref={reportRef} className="grid gap-4 md:grid-cols-2">
          <VergleichKachel
            titel={`${t("weekly.saldo")} · ${report.kw_label}`}
            infoKey="hr.weekly_saldo"
            werte={report.saldo_mehrarbeit}
            prevLabel={report.kw_prev_label}
            curLabel={report.kw_label}
            farbeNegativ
          />
          <PersonenKachel
            titel={`${t("weekly.ueberstunden")} · ${report.kw_label}`}
            infoKey="hr.weekly_ueberstunden"
            personen={report.ueberstunden_top}
            leerText={t("weekly.keineDaten")}
          />
          <VergleichKachel
            titel={`${t(krankEinheit === "tage" ? "weekly.krankheit" : "weekly.krankheitStd")} · ${report.kw_label}`}
            infoKey="hr.weekly_krankheit"
            werte={krankEinheit === "tage" ? report.krankheit_tage : report.krankheit_std}
            prevLabel={report.kw_prev_label}
            curLabel={report.kw_label}
            einheit={krankEinheit === "tage" ? t("weekly.einheitTage") : t("weekly.einheitStunden")}
            leerText={t("weekly.krankAusstehend")}
          />
          <PersonenKachel
            titel={`${t(krankEinheit === "tage" ? "weekly.krankheitProPerson" : "weekly.krankheitProPersonStd")} · ${report.kw_label}`}
            infoKey="hr.weekly_krankheit_personen"
            personen={[...report.krankheit_top]
              .map((p) => ({ name: p.name, stunden: krankEinheit === "tage" ? (p.tage ?? 0) : p.stunden }))
              .sort((a, b) => b.stunden - a.stunden)}
            einheit={krankEinheit === "tage" ? t("weekly.einheitTage") : t("weekly.einheitStunden")}
            leerText={t("weekly.krankAusstehend")}
          />
        </div>
      )}
    </section>
  );
}

function VergleichKachel({
  titel,
  werte,
  prevLabel,
  curLabel,
  farbeNegativ,
  einheit = "h",
  leerText,
  infoKey,
}: {
  titel: string;
  infoKey?: KpiInfoKey;
  werte: WochenKennzahl;
  prevLabel: string;
  curLabel: string;
  farbeNegativ?: boolean;
  einheit?: string;
  leerText?: string;
}) {
  if (werte.aktuell == null && werte.vorwoche == null) {
    return <LeerKachel titel={titel} text={leerText} infoKey={infoKey} />;
  }
  const data = [
    { kw: prevLabel, wert: werte.vorwoche ?? 0 },
    { kw: curLabel, wert: werte.aktuell ?? 0 },
  ];
  return (
    <Card className="p-4">
      <div className="mb-2 text-sm font-medium flex items-center gap-1">
        {titel}
        {infoKey && <KachelInfo infoKey={infoKey} titel={titel} />}
      </div>
      {/* Oberer Rand gibt dem Wert-Label über dem Balken Platz — die Y-Achse
          behält ihre runden Standard-Zahlen (keine krumme Domain). */}
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 24, right: 8, left: 8, bottom: 4 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="kw" {...axisProps} />
          <YAxis {...axisProps} allowDecimals={false} />
          <ReferenceLine y={0} stroke="var(--border)" />
          <Tooltip
            cursor={tooltipCursorProps}
            contentStyle={tooltipStyle}
            itemStyle={tooltipItemStyle}
            labelStyle={tooltipLabelStyle}
            formatter={(v) => [`${Number(v).toFixed(2)} ${einheit}`, ""]}
          />
          <Bar dataKey="wert" radius={[4, 4, 0, 0]} label={{ position: "top", fontSize: 11 }}>
            {data.map((d, i) => (
              <Cell
                key={i}
                fill={
                  farbeNegativ && d.wert < 0
                    ? "var(--destructive, #dc2626)"
                    : "var(--primary, #2563eb)"
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

function PersonenKachel({
  titel,
  personen,
  einheit = "h",
  leerText,
  infoKey,
}: {
  titel: string;
  infoKey?: KpiInfoKey;
  personen: WeeklyPerson[];
  einheit?: string;
  leerText?: string;
}) {
  if (!personen.length) return <LeerKachel titel={titel} text={leerText} infoKey={infoKey} />;
  return (
    <Card className="p-4">
      <div className="mb-2 text-sm font-medium flex items-center gap-1">
        {titel}
        {infoKey && <KachelInfo infoKey={infoKey} titel={titel} />}
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart
          data={personen}
          layout="vertical"
          margin={{ top: 4, right: 44, left: 8, bottom: 4 }}
        >
          <CartesianGrid {...gridProps} horizontal={false} />
          <XAxis type="number" {...axisProps} allowDecimals={false} />
          <YAxis type="category" dataKey="name" width={130} {...axisProps} />
          <Tooltip
            cursor={tooltipCursorProps}
            contentStyle={tooltipStyle}
            itemStyle={tooltipItemStyle}
            labelStyle={tooltipLabelStyle}
            formatter={(v) => [`${Number(v).toFixed(2)} ${einheit}`, ""]}
          />
          <Bar dataKey="stunden" radius={[0, 4, 4, 0]} fill="var(--primary, #2563eb)"
               label={{ position: "right", fontSize: 11, formatter: (v) => Number(v).toFixed(2) }} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

/** Info button for the report tiles; tagged so the PNG/PDF export skips it. */
function KachelInfo({ infoKey, titel }: { infoKey: KpiInfoKey; titel: string }) {
  return (
    <span data-kpi-info-ui="true">
      <KpiInfoButton infoKey={infoKey} label={titel} />
    </span>
  );
}

function LeerKachel({ titel, text, infoKey }: { titel: string; text?: string; infoKey?: KpiInfoKey }) {
  return (
    <Card className="p-4">
      <div className="mb-2 text-sm font-medium flex items-center gap-1">
        {titel}
        {infoKey && <KachelInfo infoKey={infoKey} titel={titel} />}
      </div>
      <div className="flex h-[220px] items-center justify-center text-center text-xs text-muted-foreground">
        {text}
      </div>
    </Card>
  );
}
