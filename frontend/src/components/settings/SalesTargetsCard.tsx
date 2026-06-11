import { useTranslation } from "react-i18next";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { DraftFields } from "@/hooks/useSettingsDraft";

interface SalesTargetsCardProps {
  draft: DraftFields;
  setField: <K extends keyof DraftFields>(field: K, value: DraftFields[K]) => void;
  /** When true, render without a Card wrapper — as a subsection inside a parent card. */
  embedded?: boolean;
}

// suffix = "" for counts, "€" for the angebote target.
const TARGET_FIELDS = [
  { key: "target_sales_erstkontakte" as const, labelKey: "settings.targets.sales.erstkontakte", suffix: "/ Wo." },
  { key: "target_sales_interessenten" as const, labelKey: "settings.targets.sales.interessenten", suffix: "/ Wo." },
  { key: "target_sales_besuche" as const, labelKey: "settings.targets.sales.besuche", suffix: "/ Wo." },
  { key: "target_sales_angebote_eur" as const, labelKey: "settings.targets.sales.angebote", suffix: "€ / Wo." },
  { key: "target_sales_orders_per_rep_eur" as const, labelKey: "settings.targets.sales.orders_per_rep", suffix: "€ / Wo. / VL" },
];

export function SalesTargetsCard({ draft, setField, embedded = false }: SalesTargetsCardProps) {
  const { t } = useTranslation();

  const body = (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
      {TARGET_FIELDS.map(({ key, labelKey, suffix }) => {
        const raw = draft[key];
        const displayValue = raw == null ? "" : String(raw);

        const handleChange = (input: string) => {
          if (input === "") {
            setField(key, null);
            return;
          }
          const num = parseFloat(input.replace(",", "."));
          if (isNaN(num)) return;
          setField(key, num);
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
                className="pr-16"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                {suffix}
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
            {t("settings.targets.sales.title")}
          </h3>
          <p className="text-sm text-muted-foreground">
            {t("settings.targets.sales.description")}
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
          {t("settings.targets.sales.title")}
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          {t("settings.targets.sales.description")}
        </p>
      </CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  );
}
