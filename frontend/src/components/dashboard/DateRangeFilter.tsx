import { useTranslation } from "react-i18next";
import { SegmentedControl } from "@/components/ui/segmented-control";
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

  return (
    <SegmentedControl<Preset>
      segments={PRESETS.map((p) => ({
        value: p,
        label: t(`dashboard.filter.${p}`),
      }))}
      value={preset}
      onChange={(p) => selectPreset(p)}
      aria-label="Date range"
    />
  );
}
