import { createContext, useContext, useState, type ReactNode } from "react";

interface BubbleModeState {
  active: boolean;
  toggle: () => void;
  setActive: (v: boolean) => void;
}

const BubbleModeContext = createContext<BubbleModeState | null>(null);

/** Global "add bubble" mode — when active, every KPI chart accepts a region draw. */
export function BubbleModeProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState(false);
  return (
    <BubbleModeContext.Provider
      value={{ active, setActive, toggle: () => setActive((v) => !v) }}
    >
      {children}
    </BubbleModeContext.Provider>
  );
}

export function useBubbleMode(): BubbleModeState {
  const ctx = useContext(BubbleModeContext);
  if (!ctx) return { active: false, toggle: () => {}, setActive: () => {} };
  return ctx;
}
