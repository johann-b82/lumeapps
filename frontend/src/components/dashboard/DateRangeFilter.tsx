import { useTranslation } from "react-i18next";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getPresetRange, type Preset } from "@/lib/dateUtils";

export interface DateRangeValue {
  from: Date | undefined;
  to: Date | undefined;
}

interface DateRangeFilterProps {
  value: DateRangeValue;
  preset: Preset;
  onChange: (value: DateRangeValue, preset: Preset) => void;
}

const PRESETS: Preset[] = ["thisMonth", "thisQuarter", "thisYear", "allTime"];

export function DateRangeFilter({
  value: _value,
  preset,
  onChange,
}: DateRangeFilterProps) {
  const { t } = useTranslation();

  const selectPreset = (p: Preset) => {
    const range = getPresetRange(p);
    onChange({ from: range.from, to: range.to }, p);
  };

  const segments = PRESETS.map((p) => ({
    value: p,
    label: t(`dashboard.filter.${p}`),
  }));

  // base-ui Select.Value falls back to the raw value when its render-prop
  // isn't supplied — items inside Portal/Popup may not be mounted before
  // first open, which prevents auto-label-tracking. Map value→label
  // explicitly so the trigger always shows the translated text.
  const renderLabel = (v: Preset) =>
    segments.find((s) => s.value === v)?.label ?? v;

  return (
    <Select<Preset> value={preset} onValueChange={selectPreset}>
      <SelectTrigger
        data-testid="date-range-filter-trigger"
        className="w-44"
        aria-label="Date range"
      >
        <SelectValue>{renderLabel}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {segments.map((s) => (
          <SelectItem key={s.value} value={s.value}>
            {s.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
