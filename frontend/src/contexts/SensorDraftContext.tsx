import { createContext, useContext, useState, type ReactNode } from "react";

/**
 * Phase 40-01 — lightweight dirty-status provider for /settings/sensors.
 * Mirrors SettingsDraftContext so NavBar (or other App-level consumers)
 * could read sensor-admin dirty state symmetrically with /settings.
 *
 * Only the useUnsavedGuard + page-level sync in useSensorDraft + the
 * SensorsSettingsPage effect consume this today; keeping parity with
 * SettingsDraftContext avoids future surprise if NavBar grows cross-page
 * dirty-awareness.
 */
interface SensorDraftStatus {
  isDirty: boolean;
  setDirty: (v: boolean) => void;
}

const Ctx = createContext<SensorDraftStatus | null>(null);

export function SensorDraftProvider({ children }: { children: ReactNode }) {
  const [isDirty, setDirty] = useState(false);
  return <Ctx.Provider value={{ isDirty, setDirty }}>{children}</Ctx.Provider>;
}

/**
 * Returns null when the consumer is outside the provider (impossible if
 * App.tsx wraps). Consumers should null-coalesce and default to enabled.
 */
export function useSensorDraftStatus(): SensorDraftStatus | null {
  return useContext(Ctx);
}
