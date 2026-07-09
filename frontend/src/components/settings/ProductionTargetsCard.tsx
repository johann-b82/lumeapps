import { useTranslation } from "react-i18next";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { DraftFields } from "@/hooks/useSettingsDraft";

interface ProductionTargetsCardProps {
  draft: DraftFields;
  setField: <K extends keyof DraftFields>(field: K, value: DraftFields[K]) => void;
  embedded?: boolean;
}

// Mirrors FinanceTargetsCard: the Verzug target is a fraction (0.20 = 20 %)
// and edited as a percent — the max acceptable Verzugsquote, drawn as a
// reference line on the Verzugsquote chart.
const TARGET_FIELDS = [
  {
    key: "target_produktion_verzug" as const,
    labelKey: "settings.targets.production.verzug",
    isPercent: true,
  },
];

export function ProductionTargetsCard({
  draft,
  setField,
  embedded = false,
}: ProductionTargetsCardProps) {
  const { t } = useTranslation();

  const body = (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {TARGET_FIELDS.map(({ key, labelKey, isPercent }) => {
        const raw = draft[key];
        const displayValue =
          raw == null
            ? ""
            : isPercent
            ? String(Math.round((raw as number) * 10000) / 100)
            : String(raw);

        const handleChange = (input: string) => {
          if (input === "") {
            setField(key, null);
            return;
          }
          const num = parseFloat(input.replace(",", "."));
          if (isNaN(num)) return;
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
                className="pr-12"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                %
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );

  if (embedded) {
    return (
      <section className="space-y-4">
        <div>
          <h3 className="text-xl font-semibold">
            {t("settings.targets.production.title")}
          </h3>
          <p className="text-sm text-muted-foreground">
            {t("settings.targets.production.description")}
          </p>
        </div>
        {body}
      </section>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl font-semibold">
          {t("settings.targets.production.title")}
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          {t("settings.targets.production.description")}
        </p>
      </CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  );
}
