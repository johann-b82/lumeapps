import { useTranslation } from "react-i18next";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { SensorDraftGlobals } from "@/hooks/useSensorDraft";

export interface ThresholdCardProps {
  globals: SensorDraftGlobals;
  setGlobal: <K extends keyof SensorDraftGlobals>(
    key: K,
    value: SensorDraftGlobals[K],
  ) => void;
}

/**
 * Phase 40-01 — four optional threshold inputs (SEN-ADM-05).
 *
 * Known limitation documented alongside the plan: a blank input in draft
 * means "don't change" on PUT — admin cannot clear a previously-set
 * threshold through blanking alone (carry-forward for 40-02 or a dedicated
 * reset path). Description copy calls this out.
 */
export function ThresholdCard({ globals, setGlobal }: ThresholdCardProps) {
  const { t } = useTranslation();
  const fields: Array<{
    key: keyof SensorDraftGlobals;
    i18nKey: string;
  }> = [
    { key: "sensor_temperature_min", i18nKey: "sensors.admin.thresholds.temp_min" },
    { key: "sensor_temperature_max", i18nKey: "sensors.admin.thresholds.temp_max" },
    { key: "sensor_humidity_min", i18nKey: "sensors.admin.thresholds.humidity_min" },
    { key: "sensor_humidity_max", i18nKey: "sensors.admin.thresholds.humidity_max" },
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl font-semibold">
          {t("sensors.admin.thresholds.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">
          {t("sensors.admin.thresholds.description")}
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {fields.map(({ key, i18nKey }) => (
            <div key={key} className="flex flex-col gap-2">
              <Label htmlFor={`threshold-${key}`} className="text-sm font-medium">
                {t(i18nKey)}
              </Label>
              <Input
                id={`threshold-${key}`}
                type="number"
                step="0.1"
                value={globals[key] as string}
                onChange={(e) => setGlobal(key, e.target.value as never)}
              />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
