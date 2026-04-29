import { useEffect, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useSettings } from "@/hooks/useSettings";
import { DEFAULT_SETTINGS, THEME_TOKEN_MAP } from "@/lib/defaults";
import type { Settings } from "@/lib/api";

// Surface tokens: applied only in light mode; .dark CSS block handles dark mode (D-01, D-03)
const SURFACE_TOKEN_KEYS = [
  "color_background",
  "color_foreground",
  "color_muted",
  "color_destructive",
] as const satisfies ReadonlyArray<keyof typeof THEME_TOKEN_MAP>;

// Accent tokens: always applied regardless of mode (D-02, DM-04)
const ACCENT_TOKEN_KEYS = [
  "color_primary",
  "color_accent",
] as const satisfies ReadonlyArray<keyof typeof THEME_TOKEN_MAP>;

function applyTheme(settings: Settings) {
  const root = document.documentElement;
  const isDark = root.classList.contains("dark");

  // DM-04 / D-02: Always apply accent tokens regardless of mode
  ACCENT_TOKEN_KEYS.forEach((key) => {
    root.style.setProperty(THEME_TOKEN_MAP[key], settings[key]);
  });

  if (isDark) {
    // D-01 / D-03: Remove surface inline styles so .dark CSS block wins
    SURFACE_TOKEN_KEYS.forEach((key) => {
      root.style.removeProperty(THEME_TOKEN_MAP[key]);
    });
  } else {
    // Light mode: apply brand surface tokens inline
    SURFACE_TOKEN_KEYS.forEach((key) => {
      root.style.setProperty(THEME_TOKEN_MAP[key], settings[key]);
    });
  }

  document.title = settings.app_name;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { data, error } = useSettings();
  const { t } = useTranslation();
  const errorToastFired = useRef(false);

  // Render children immediately with defaults; apply real settings when they
  // arrive. Blocking on isLoading deadlocks unauthenticated cold-loads where
  // /api/settings 401s before the user reaches /login (Phase 28 gated the
  // endpoint on auth).
  const effective: Settings = data ?? DEFAULT_SETTINGS;

  useEffect(() => {
    applyTheme(effective);

    // D-14: Watch for external .dark class changes (devtools in Phase 21, toggle in Phase 22)
    const observer = new MutationObserver(() => {
      applyTheme(effective);
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => observer.disconnect();
  }, [effective]);

  useEffect(() => {
    if (error && !errorToastFired.current) {
      toast.error(t("theme.error_toast"));
      errorToastFired.current = true;
    }
  }, [error, t]);

  return <>{children}</>;
}
