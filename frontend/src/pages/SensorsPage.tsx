import { SensorStatusCards } from "@/components/sensors/SensorStatusCards";
import { SensorTimeSeriesChart } from "@/components/sensors/SensorTimeSeriesChart";

/**
 * SensorsPage — Phase 58 chrome-parity shell.
 *
 * Time-window picker and poll action now live in the SubHeader on /sensors
 * (Phase 58 D-03/D-04). The time-window provider is hoisted to App.tsx
 * (Phase 58 D-01) so both chrome and body read the same useSensorWindow()
 * context. This page body is now pure data presentation.
 */
export function SensorsPage() {
  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8 space-y-8">
      <SensorStatusCards />
      <SensorTimeSeriesChart />
    </div>
  );
}
