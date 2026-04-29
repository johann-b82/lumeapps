import { useTranslation } from "react-i18next";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { DraftFields } from "@/hooks/useSettingsDraft";

interface HrTargetsCardProps {
  draft: DraftFields;
  setField: <K extends keyof DraftFields>(field: K, value: DraftFields[K]) => void;
  /** When true, render without a Card wrapper — as a subsection inside a parent card. */
  embedded?: boolean;
}

const TARGET_FIELDS = [
  { key: "target_overtime_ratio" as const, labelKey: "settings.targets.overtime", isPercent: true },
  { key: "target_sick_leave_ratio" as const, labelKey: "settings.targets.sick_leave", isPercent: true },
  { key: "target_fluctuation" as const, labelKey: "settings.targets.fluctuation", isPercent: true },
  { key: "target_revenue_per_employee" as const, labelKey: "settings.targets.revenue", isPercent: false },
];

export function HrTargetsCard({ draft, setField, embedded = false }: HrTargetsCardProps) {
  const { t } = useTranslation();

  const body = (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {TARGET_FIELDS.map(({ key, labelKey, isPercent }) => {
            const raw = draft[key];
            // Display: ratio → percent for display, raw number for currency
            const displayValue =
              raw == null ? "" : isPercent ? String(Math.round(raw * 10000) / 100) : String(raw);

            const handleChange = (input: string) => {
              if (input === "") {
                setField(key, null);
                return;
              }
              const num = parseFloat(input.replace(",", "."));
              if (isNaN(num)) return;
              // Store: percent → ratio, currency as-is
              setField(key, isPercent ? num / 100 : num);
            };

            return (
              <div key={key} className="flex flex-col gap-1.5">
                <Label className="text-sm font-medium">{t(labelKey)}</Label>
                <div className="relative">
                  <Input
                    type="text"
                    inputMode="decimal"
                    value={displayValue}
                    onChange={(e) => handleChange(e.target.value)}
                    placeholder="—"
                    className="pr-8"
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                    {isPercent ? "%" : "€"}
                  </span>
                </div>
              </div>
            );
          })}
      </div>
    </>
  );

  if (embedded) {
    return (
      <section className="space-y-4">
        <div>
          <h3 className="text-base font-semibold">
            {t("settings.targets.title")}
          </h3>
          <p className="text-sm text-muted-foreground">
            {t("settings.targets.description")}
          </p>
        </div>
        {body}
      </section>
    );
  }

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="text-xl font-semibold">
          {t("settings.targets.title")}
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          {t("settings.targets.description")}
        </p>
      </CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  );
}
