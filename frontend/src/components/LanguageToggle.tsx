import { useTranslation } from "react-i18next";
import { Toggle } from "@/components/ui/toggle";

/**
 * NavBar language toggle — 2-segment Toggle showing DE and EN,
 * with the currently-active language highlighted. Click or keyboard-activate
 * the inactive segment to switch. Persists via i18next (no server round-trip).
 *
 * Phase 54 D-11 pattern: visual layer migrated to Toggle; language-switch
 * logic (i18n.changeLanguage) preserved verbatim. TOGGLE-02 acceptance.
 */
type Language = "de" | "en";

export function LanguageToggle() {
  const { i18n } = useTranslation();
  const current: Language = i18n.language === "de" ? "de" : "en";

  return (
    <Toggle<Language>
      segments={[
        { value: "de", label: "DE" },
        { value: "en", label: "EN" },
      ] as const}
      value={current}
      onChange={(next) => void i18n.changeLanguage(next)}
      aria-label="Language"
      variant="muted"
    />
  );
}
