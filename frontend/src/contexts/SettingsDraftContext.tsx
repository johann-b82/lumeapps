import { createContext, useContext, useState, type ReactNode } from "react";

interface SettingsDraftStatus {
  isDirty: boolean;
  setDirty: (v: boolean) => void;
}

const Ctx = createContext<SettingsDraftStatus | null>(null);

export function SettingsDraftProvider({ children }: { children: ReactNode }) {
  const [isDirty, setDirty] = useState(false);
  return <Ctx.Provider value={{ isDirty, setDirty }}>{children}</Ctx.Provider>;
}

// Returns null when the consumer is outside the provider (impossible if App wraps).
// Consumers read .isDirty to decide disable state; null-coalescing defaults to enabled.
export function useSettingsDraftStatus(): SettingsDraftStatus | null {
  return useContext(Ctx);
}
