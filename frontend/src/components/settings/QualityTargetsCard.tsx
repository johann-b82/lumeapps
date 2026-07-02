import { useTranslation } from "react-i18next";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { DraftFields } from "@/hooks/useSettingsDraft";

interface QualityTargetsCardProps {
  draft: DraftFields;
  setField: <K extends keyof DraftFields>(field: K, value: DraftFields[K]) => void;
  embedded?: boolean;
}

// Same shape as HrTargetsCard: each row is one field. `isPercent` controls
// the ratio↔percent display conversion; `isInteger` switches the input
// validation and the "Stück" suffix vs. the "%" one.
const TARGET_FIELDS = [
  {
    key: "target_complaint_rate_customer" as const,
    labelKey: "settings.targets.quality.customer",
    isPercent: true,
    isInteger: false,
  },
  {
    key: "target_complaint_rate_internal" as const,
    labelKey: "settings.targets.quality.internal",
    isPercent: true,
    isInteger: false,
  },
  {
    key: "target_complaint_rate_supplier" as const,
    labelKey: "settings.targets.quality.supplier",
    isPercent: true,
    isInteger: false,
  },
  {
    key: "target_complaint_rate_subcontractor" as const,
    labelKey: "settings.targets.quality.subcontractor",
    isPercent: true,
    isInteger: false,
  },
  {
    key: "target_audit_findings_level1" as const,
    labelKey: "settings.targets.quality.level1",
    isPercent: false,
    isInteger: true,
  },
  {
    key: "target_audit_findings_level2" as const,
    labelKey: "settings.targets.quality.level2",
    isPercent: false,
    isInteger: true,
  },
];

export function QualityTargetsCard({
  draft,
  setField,
  embedded = false,
}: QualityTargetsCardProps) {
  const { t } = useTranslation();

  const body = (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {TARGET_FIELDS.map(({ key, labelKey, isPercent, isInteger }) => {
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
          if (isInteger) {
            setField(key, Math.round(num));
            return;
          }
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
                {isPercent ? "%" : t("quality.unit.count")}
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
            {t("settings.targets.quality.title")}
          </h3>
          <p className="text-sm text-muted-foreground">
            {t("settings.targets.quality.description")}
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
          {t("settings.targets.quality.title")}
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          {t("settings.targets.quality.description")}
        </p>
      </CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  );
}
