// Phase 47 — i18n Path B (Pitfall P9 resolution): hard-coded EN+DE for the 5 player strings.
// Bundle-size discipline: i18next costs ~25KB for ~150 bytes of text. Path B saves the budget.
// CI parity: see frontend/scripts/check-player-isolation.mjs (Plan 47-05 adds a strings-parity test).
// Source-of-truth pairs MUST stay byte-for-byte identical with what UI-SPEC §Copywriting documents.

import { playerLang, type PlayerLang } from "./locale";

type Key =
  | "pair.headline"
  | "pair.hint"
  | "pair.code_placeholder"
  | "offline.label"
  | "offline.aria_label";

const STRINGS: Record<PlayerLang, Record<Key, string>> = {
  en: {
    "pair.headline": "Pair this device",
    "pair.hint": "Enter this code in the admin panel under Signage → Devices → Pair new device",
    "pair.code_placeholder": "—",
    "offline.label": "Offline",
    "offline.aria_label": "Player is offline; cached content is playing",
  },
  de: {
    "pair.headline": "Verbinde dieses Gerät",
    "pair.hint": "Gib diesen Code im Admin-Panel unter Signage → Geräte → Neues Gerät koppeln ein",
    "pair.code_placeholder": "—",
    "offline.label": "Offline",
    "offline.aria_label": "Wiedergabe läuft offline; Inhalte werden aus dem Cache gespielt",
  },
};

export function t(key: Key): string {
  return STRINGS[playerLang][key];
}

// Exported so the parity test (Plan 47-05) can introspect.
export { STRINGS };
