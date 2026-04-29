import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

/**
 * Phase 52 Plan 02 — 7-checkbox weekday row + 3 quick-pick chips.
 *
 * Adapter contract (see scheduleAdapters.ts): bit0=Mo..bit6=So.
 * UI order matches German week start: Mo, Di, Mi, Do, Fr, Sa, So.
 *
 * Quick-pick buttons OVERWRITE the current checkbox state (D-05 — not
 * a union) so the operator can flip between presets without clearing
 * by hand.
 */
export interface WeekdayCheckboxRowProps {
  value: boolean[];
  onChange: (next: boolean[]) => void;
  id?: string;
  error?: boolean;
}

const WEEKDAY_KEYS = [
  "signage.admin.schedules.weekday.mo",
  "signage.admin.schedules.weekday.tu",
  "signage.admin.schedules.weekday.we",
  "signage.admin.schedules.weekday.th",
  "signage.admin.schedules.weekday.fr",
  "signage.admin.schedules.weekday.sa",
  "signage.admin.schedules.weekday.su",
] as const;

const PRESET_WEEKDAYS: boolean[] = [true, true, true, true, true, false, false];
const PRESET_WEEKEND: boolean[] = [false, false, false, false, false, true, true];
const PRESET_DAILY: boolean[] = [true, true, true, true, true, true, true];

export function WeekdayCheckboxRow({
  value,
  onChange,
  id,
  error,
}: WeekdayCheckboxRowProps) {
  const { t } = useTranslation();

  const setAt = (i: number, checked: boolean) => {
    const next = value.slice();
    next[i] = checked;
    onChange(next);
  };

  return (
    <div className="space-y-3" id={id}>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => onChange(PRESET_WEEKDAYS.slice())}
        >
          {t("signage.admin.schedules.quickpick.weekdays")}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => onChange(PRESET_WEEKEND.slice())}
        >
          {t("signage.admin.schedules.quickpick.weekend")}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => onChange(PRESET_DAILY.slice())}
        >
          {t("signage.admin.schedules.quickpick.daily")}
        </Button>
      </div>
      <div
        className={
          error
            ? "flex flex-wrap gap-4 text-sm text-destructive"
            : "flex flex-wrap gap-4 text-sm text-muted-foreground"
        }
      >
        {WEEKDAY_KEYS.map((key, i) => {
          const cbId = id ? `${id}-wd-${i}` : `wd-${i}`;
          return (
            <label
              key={key}
              htmlFor={cbId}
              className="flex items-center gap-2 cursor-pointer"
            >
              <Checkbox
                id={cbId}
                checked={value[i] ?? false}
                onCheckedChange={(c) => setAt(i, c === true)}
              />
              <span>{t(key)}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
