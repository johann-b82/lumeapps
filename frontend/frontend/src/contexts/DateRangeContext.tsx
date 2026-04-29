import { createContext, useContext, useState, type ReactNode } from "react";
import { getPresetRange, type Preset } from "@/lib/dateUtils";
import type { DateRangeValue } from "@/components/dashboard/DateRangeFilter";

interface DateRangeContextValue {
  preset: Preset;
  range: DateRangeValue;
  handleFilterChange: (next: DateRangeValue, nextPreset: Preset) => void;
}

const Ctx = createContext<DateRangeContextValue | null>(null);

export function DateRangeProvider({ children }: { children: ReactNode }) {
  const [preset, setPreset] = useState<Preset>("thisYear");
  const [range, setRange] = useState<DateRangeValue>(() => {
    const initial = getPresetRange("thisYear");
    return { from: initial.from, to: initial.to };
  });

  const handleFilterChange = (next: DateRangeValue, nextPreset: Preset) => {
    setRange(next);
    setPreset(nextPreset);
  };

  return (
    <Ctx.Provider value={{ preset, range, handleFilterChange }}>
      {children}
    </Ctx.Provider>
  );
}

export function useDateRange(): DateRangeContextValue {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useDateRange must be used within DateRangeProvider");
  return ctx;
}
