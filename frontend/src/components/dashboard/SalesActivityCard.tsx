import { useTranslation } from "react-i18next";
import {
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { sensorPalette } from "@/lib/chartDefaults";
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
  empIds: number[],
  kpi: keyof ContactsWeeklyEmployeeBucket,
): Array<Record<string, number | string>> {
  return data.weeks.map((w) => {
    const row: Record<string, number | string> = { label: w.label };
    for (const id of empIds) {
      row[String(id)] = w.per_employee[id]?.[kpi] ?? 0;
    }
    return row;
  });
}

export function SalesActivityCard({ startDate, endDate }: Props) {
  const { t } = useTranslation();
  const q = useContactsWeekly(startDate ?? "", endDate ?? "");

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

  const empIds = Object.keys(q.data.employees)
    .map(Number)
    .sort((a, b) => a - b);

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
                <LineChart data={buildSeries(q.data!, empIds, k.key)}>
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  {idx === 0 && <Legend wrapperStyle={{ fontSize: 11 }} />}
                  {empIds.map((id, i) => (
                    <Line
                      key={id}
                      type="monotone"
                      dataKey={String(id)}
                      name={q.data!.employees[id]}
                      stroke={sensorPalette[i % sensorPalette.length]}
                      strokeWidth={2}
                      dot={false}
                      isAnimationActive={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
