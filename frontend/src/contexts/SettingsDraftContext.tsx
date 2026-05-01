import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

export type SettingsSection = "general" | "hr" | "sensors";

interface SettingsDraftStatus {
  isDirty: boolean;
  setDirty: (v: boolean) => void;
  pendingSection: SettingsSection | null;
  /**
   * Request a navigation to a sibling settings section.
   * - If !isDirty: invokes `commit("/settings/<section>")` immediately so the
   *   caller (SubHeader picker) can fire wouter.navigate.
   * - If isDirty: stores `section` in `pendingSection` so the active page
   *   can open its UnsavedChangesDialog. The page is responsible for
   *   calling navigate + clearPendingSection on confirm, or
   *   clearPendingSection alone on cancel.
   */
  requestSectionChange: (
    section: SettingsSection,
    commit: (dest: string) => void,
  ) => void;
  clearPendingSection: () => void;
}

const Ctx = createContext<SettingsDraftStatus | null>(null);

export function SettingsDraftProvider({ children }: { children: ReactNode }) {
  const [isDirty, setDirty] = useState(false);
  const [pendingSection, setPendingSection] = useState<SettingsSection | null>(null);

  const requestSectionChange = useCallback(
    (section: SettingsSection, commit: (dest: string) => void) => {
      if (isDirty) {
        setPendingSection(section);
      } else {
        commit(`/settings/${section}`);
      }
    },
    [isDirty],
  );

  const clearPendingSection = useCallback(() => {
    setPendingSection(null);
  }, []);

  return (
    <Ctx.Provider
      value={{
        isDirty,
        setDirty,
        pendingSection,
        requestSectionChange,
        clearPendingSection,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useSettingsDraftStatus(): SettingsDraftStatus | null {
  return useContext(Ctx);
}
