import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Sun, Moon } from "lucide-react";
import { Toggle } from "@/components/ui/toggle";

/**
 * Theme switch — 2-segment Toggle with sun (light) and moon (dark) icons.
 * Persists to localStorage.theme and toggles the .dark class on <html>.
 * Live-tracks OS prefers-color-scheme until the user picks a theme (D-06, D-07).
 * Phase 54 D-11: visual layer migrated to Toggle; all persistence/OS logic preserved.
 */
type ThemeMode = "light" | "dark";

export function ThemeToggle() {
  const { t } = useTranslation();
  const [mode, setMode] = useState<ThemeMode>(() =>
    document.documentElement.classList.contains("dark") ? "dark" : "light",
  );

  const applyMode = (next: ThemeMode, persist: boolean) => {
    const root = document.documentElement;
    if (next === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    if (persist) localStorage.setItem("theme", next);
    setMode(next);
  };

  useEffect(() => {
    const mql = window.matchMedia('(prefers-color-scheme: dark)');
    const onOsChange = (e: MediaQueryListEvent) => {
      const stored = localStorage.getItem("theme");
      // D-07: localStorage wins permanently once set
      if (stored === "light" || stored === "dark") return;
      applyMode(e.matches ? "dark" : "light", false);
    };
    mql.addEventListener("change", onOsChange);
    return () => mql.removeEventListener("change", onOsChange);
  }, []);

  return (
    <Toggle<ThemeMode>
      segments={[
        { value: "light", icon: <Sun className="h-4 w-4" aria-hidden="true" /> },
        { value: "dark", icon: <Moon className="h-4 w-4" aria-hidden="true" /> },
      ] as const}
      value={mode}
      onChange={(next) => applyMode(next, true)}
      aria-label={t("theme.toggle.aria_label")}
      variant="muted"
    />
  );
}
