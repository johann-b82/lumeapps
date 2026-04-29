import { useTranslation } from "react-i18next";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export interface PollIntervalCardProps {
  value: number;
  onChange: (value: number) => void;
}

/**
 * Phase 40-01 — polling-interval input (SEN-ADM-04).
 * Bounds 5..86400 enforced by Pydantic on PUT; inline error surfaces early.
 */
export function PollIntervalCard({ value, onChange }: PollIntervalCardProps) {
  const { t } = useTranslation();
  const outOfBounds = value < 5 || value > 86400;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl font-semibold">
          {t("sensors.admin.poll_interval.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-2 max-w-sm">
          <Label htmlFor="sensor-poll-interval" className="text-sm font-medium">
            {t("sensors.admin.poll_interval.label")}
          </Label>
          <Input
            id="sensor-poll-interval"
            type="number"
            min={5}
            max={86400}
            step={1}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
          />
          {outOfBounds ? (
            <p className="text-xs text-destructive">
              {t("sensors.admin.poll_interval.out_of_bounds")}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              {t("sensors.admin.poll_interval.help")}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
