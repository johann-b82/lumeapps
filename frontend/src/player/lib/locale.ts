// Phase 47 D-3: navigator.language → 'de' | 'en' picker.
// Detected once at module load — no re-render flicker.

export type PlayerLang = "de" | "en";

export const playerLang: PlayerLang =
  typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("de")
    ? "de"
    : "en";
