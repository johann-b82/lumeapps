import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/**
 * SensorTimeWindow — Phase 39 local time-window state for the Sensors page.
 *
 * D-06: Do NOT reuse DateRangeContext (absolute-date-range-based; wrong shape).
 * This context is scoped to SensorsPage so cards + charts + freshness all read
 * the same value without prop drilling. Default is "24h".
 */
export type SensorWindow = "1h" | "6h" | "24h" | "7d" | "30d";

export const SENSOR_WINDOWS: SensorWindow[] = ["1h", "6h", "24h", "7d", "30d"];

export function windowToHours(w: SensorWindow): number {
  const map: Record<SensorWindow, number> = {
    "1h": 1,
    "6h": 6,
    "24h": 24,
    "7d": 168,
    "30d": 720,
  };
  return map[w];
}

interface SensorTimeWindowContextValue {
  window: SensorWindow;
  setWindow: (w: SensorWindow) => void;
}

const SensorTimeWindowContext = createContext<
  SensorTimeWindowContextValue | undefined
>(undefined);

export function SensorTimeWindowProvider({ children }: { children: ReactNode }) {
  const [window, setWindow] = useState<SensorWindow>("24h");
  const value = useMemo(() => ({ window, setWindow }), [window]);
  return (
    <SensorTimeWindowContext.Provider value={value}>
      {children}
    </SensorTimeWindowContext.Provider>
  );
}

export function useSensorWindow(): SensorTimeWindowContextValue {
  const ctx = useContext(SensorTimeWindowContext);
  if (!ctx) {
    throw new Error(
      "useSensorWindow must be used inside <SensorTimeWindowProvider>",
    );
  }
  return ctx;
}

export function SensorTimeWindowPicker() {
  const { t } = useTranslation();
  const { window, setWindow } = useSensorWindow();
  const segments = SENSOR_WINDOWS.map((w) => ({
    value: w,
    label: t(`sensors.window.${w}`),
  }));
  const renderLabel = (v: SensorWindow) =>
    segments.find((s) => s.value === v)?.label ?? v;
  return (
    <Select<SensorWindow> value={window} onValueChange={setWindow}>
      <SelectTrigger
        data-testid="sensor-time-window-trigger"
        className="w-32"
        aria-label={t("sensors.window.aria")}
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
