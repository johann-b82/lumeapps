import { useLocation } from "wouter";
import type { SettingsSection } from "@/contexts/SettingsDraftContext";

const KNOWN: ReadonlySet<SettingsSection> = new Set(["general", "hr", "sensors"]);

interface UseSettingsSectionReturn {
  section: SettingsSection;
}

/**
 * Parse the active settings section from the wouter location.
 * - /settings              → "general" (the redirect target)
 * - /settings/general      → "general"
 * - /settings/hr           → "hr"
 * - /settings/sensors      → "sensors"
 * - /settings/<unknown>    → "general" (defensive — never throws)
 */
export function useSettingsSection(): UseSettingsSectionReturn {
  const [path] = useLocation();
  const segs = path.split("/").filter(Boolean);
  const candidate = (segs[1] ?? "general") as SettingsSection;
  const section: SettingsSection = KNOWN.has(candidate) ? candidate : "general";
  return { section };
}
