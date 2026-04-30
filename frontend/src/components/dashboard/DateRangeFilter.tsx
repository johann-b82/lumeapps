import { useTranslation } from "react-i18next";
import { SegmentedControl } from "@/components/ui/segmented-control";
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

  return (
    <>
      <div data-testid="date-range-filter-desktop" className="hidden md:block">
        <SegmentedControl<Preset>
          segments={segments}
          value={preset}
          onChange={selectPreset}
          aria-label="Date range"
        />
      </div>
      <div data-testid="date-range-filter-mobile" className="md:hidden">
        <Select<Preset>
          value={preset}
          onValueChange={selectPreset}
        >
          <SelectTrigger className="w-44" aria-label="Date range">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {segments.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </>
  );
}
