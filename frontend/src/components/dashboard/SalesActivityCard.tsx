import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  Bar,
  BarChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { primaryPalette } from "@/lib/chartDefaults";
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

function buildSeries(
  data: ContactsWeeklyResponse,
  tokens: string[],
  kpi: keyof ContactsWeeklyEmployeeBucket,
): Array<Record<string, number | string>> {
  return data.weeks.map((w) => {
    const row: Record<string, number | string> = { label: w.label };
    for (const tk of tokens) {
      row[tk] = w.per_employee[tk]?.[kpi] ?? 0;
    }
    return row;
  });
}

function collectTokens(weeks: ContactsWeeklyResponse["weeks"]): string[] {
  const set = new Set<string>();
  for (const w of weeks) {
    for (const tk of Object.keys(w.per_employee)) set.add(tk);
  }
  return [...set].sort();
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
        {KPIS.map((k, idx) => (
          <div key={k.key} className="flex flex-col">
            <div className="text-sm font-medium mb-2">{t(k.titleKey)}</div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={buildSeries(q.data!, tokens, k.key)}>
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  {idx === 0 && <Legend wrapperStyle={{ fontSize: 11 }} />}
                  {tokens.map((tk, i) => (
                    <Bar
                      key={tk}
                      dataKey={tk}
                      name={tk}
                      fill={primaryPalette[i % primaryPalette.length]}
                      stackId="reps"
                      isAnimationActive={false}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
