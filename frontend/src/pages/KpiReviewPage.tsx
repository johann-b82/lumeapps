import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Loader2, MessageSquare, ListChecks } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KpiDetailPanel } from "@/components/kpireview/KpiDetailPanel";
import { kpiReviewKeys } from "@/lib/queryKeys";
import {
  fetchKpiSummary,
  fetchKpiMeasures,
  type KpiRating,
  type KpiMeasureStatus,
} from "@/lib/api";

const RATING_DOT: Record<KpiRating, string> = {
  red: "var(--color-destructive)",
  yellow: "#eab308",
  green: "#22c55e",
};
const DOMAIN_ORDER = ["sales", "hr", "quality", "finance", "procurement", "production"];
const OPEN_STATES: KpiMeasureStatus[] = ["open", "in_progress"];

export function KpiReviewPage() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const [selected, setSelected] = useState<string | null>(null);

  const summary = useQuery({
    queryKey: kpiReviewKeys.summary(),
    queryFn: fetchKpiSummary,
  });
  const allMeasures = useQuery({
    queryKey: kpiReviewKeys.measures(),
    queryFn: () => fetchKpiMeasures(),
  });

  const byDomain = useMemo(() => {
    const map = new Map<string, NonNullable<typeof summary.data>>();
    for (const it of summary.data ?? []) {
      if (!map.has(it.domain)) map.set(it.domain, []);
      map.get(it.domain)!.push(it);
    }
    return map;
  }, [summary.data]);

  const openMeasures = (allMeasures.data ?? []).filter((m) =>
    OPEN_STATES.includes(m.status),
  );
  const kpiLabel = (key: string) => t(`kpireview.kpi.${key}`);
  const fmtDate = (d: string | null) =>
    d ? new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(d)) : "—";

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-16 space-y-6">
      <div>
        <h2 className="text-xl font-semibold">{t("kpireview.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("kpireview.subtitle")}</p>
      </div>

      {summary.isLoading && (
        <div className="flex justify-center py-10">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* KPI-Kacheln je Domäne */}
      {DOMAIN_ORDER.filter((d) => byDomain.has(d)).map((domain) => (
        <section key={domain} className="space-y-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            {t(`kpireview.domain.${domain}`)}
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {byDomain.get(domain)!.map((it) => {
              const active = selected === it.kpi_key;
              return (
                <button
                  key={it.kpi_key}
                  onClick={() => setSelected(active ? null : it.kpi_key)}
                  className={`flex items-center gap-3 rounded-lg border p-3 text-left transition-colors ${
                    active
                      ? "border-primary bg-primary/5"
                      : "border-border hover:bg-muted/50"
                  }`}
                >
                  <span
                    className="inline-block h-3 w-3 shrink-0 rounded-full"
                    style={{
                      background: it.last_rating ? RATING_DOT[it.last_rating] : "var(--color-muted)",
                    }}
                    aria-hidden
                  />
                  <span className="min-w-0 flex-1 text-sm font-medium truncate">
                    {kpiLabel(it.kpi_key)}
                  </span>
                  <span className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                      <MessageSquare className="h-3.5 w-3.5" />
                      {it.comment_count}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <ListChecks className="h-3.5 w-3.5" />
                      {it.open_measure_count}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      ))}

      {/* Detail der ausgewählten KPI */}
      {selected && <KpiDetailPanel kpiKey={selected} label={kpiLabel(selected)} />}

      {/* Zentraler Maßnahmen-Tracker (offene über alle KPIs) */}
      <Card className="p-6">
        <p className="text-lg font-semibold mb-3">
          {t("kpireview.tracker.title")}{" "}
          <span className="text-sm font-normal text-muted-foreground">
            ({openMeasures.length})
          </span>
        </p>
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50 text-left">
                <th className="px-3 py-2 font-medium">{t("kpireview.tracker.kpi")}</th>
                <th className="px-3 py-2 font-medium">{t("kpireview.tracker.measure")}</th>
                <th className="px-3 py-2 font-medium">{t("kpireview.tracker.assignee")}</th>
                <th className="px-3 py-2 font-medium">{t("kpireview.tracker.due")}</th>
                <th className="px-3 py-2 font-medium">{t("kpireview.tracker.status")}</th>
              </tr>
            </thead>
            <tbody>
              {openMeasures.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-3 py-8 text-center text-muted-foreground">
                    {t("kpireview.tracker.empty")}
                  </td>
                </tr>
              ) : (
                openMeasures.map((m) => (
                  <tr
                    key={m.id}
                    className="border-b border-border last:border-0 hover:bg-muted/30 cursor-pointer"
                    onClick={() => setSelected(m.kpi_key)}
                  >
                    <td className="px-3 py-2 text-muted-foreground">{kpiLabel(m.kpi_key)}</td>
                    <td className="px-3 py-2 font-medium">{m.title}</td>
                    <td className="px-3 py-2">{m.assignee_name ?? "—"}</td>
                    <td className="px-3 py-2 whitespace-nowrap">{fmtDate(m.due_date)}</td>
                    <td className="px-3 py-2">
                      <Badge variant={m.status === "open" ? "default" : "secondary"}>
                        {t(`kpireview.status.${m.status}`)}
                      </Badge>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
