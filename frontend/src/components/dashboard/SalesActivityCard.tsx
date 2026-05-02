import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

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

const KPIS: { key: keyof ContactsWeeklyEmployeeBucket; titleKey: string }[] = [
  { key: "erstkontakte", titleKey: "sales.kpi.erstkontakte" },
  { key: "interessenten", titleKey: "sales.kpi.interessenten" },
  { key: "visits", titleKey: "sales.kpi.visits" },
  { key: "angebote", titleKey: "sales.kpi.angebote" },
];

type Row = { label: string; total: number; perRep: Record<string, number> };

function buildSeries(
  data: ContactsWeeklyResponse,
  tokens: string[],
  kpi: keyof ContactsWeeklyEmployeeBucket,
): Row[] {
  return data.weeks.map((w) => {
    const perRep: Record<string, number> = {};
    let total = 0;
    for (const tk of tokens) {
      const v = w.per_employee[tk]?.[kpi] ?? 0;
      perRep[tk] = v;
      total += v;
    }
    const label = `KW ${String(w.iso_week).padStart(2, "0")}`;
    return { label, total, perRep };
  });
}

function collectTokens(weeks: ContactsWeeklyResponse["weeks"]): string[] {
  const set = new Set<string>();
  for (const w of weeks) {
    for (const tk of Object.keys(w.per_employee)) set.add(tk);
  }
  return [...set].sort();
}

interface TooltipPayloadItem {
  payload?: Row;
}

function PerRepTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
}) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  const reps = Object.entries(row.perRep);
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-sm">
      <div className="mb-1 font-medium">{row.label}</div>
      <div className="mb-1 flex justify-between gap-4">
        <span className="text-muted-foreground">Gesamt</span>
        <span className="font-medium">{row.total}</span>
      </div>
      {reps.map(([tk, v]) => (
        <div key={tk} className="flex justify-between gap-4">
          <span className="text-muted-foreground">{tk}</span>
          <span>{v}</span>
        </div>
      ))}
    </div>
  );
}

export function SalesActivityCard({ startDate, endDate }: Props) {
  const { t } = useTranslation();
  const q = useContactsWeekly(startDate ?? "", endDate ?? "");

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
        {KPIS.map((k) => (
          <div key={k.key} className="flex flex-col">
            <div className="text-sm font-medium mb-2">{t(k.titleKey)}</div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={buildSeries(q.data!, tokens, k.key)}>
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip
                    cursor={{ fill: "var(--color-muted)", opacity: 0.5 }}
                    content={<PerRepTooltip />}
                  />
                  <Bar
                    dataKey="total"
                    fill="var(--primary)"
                    isAnimationActive={false}
                    activeBar={{ fill: "var(--color-muted)" }}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
