/**
 * Abteilungskürzel → Vollwort.
 *
 * Quelle: vom Betrieb gelieferte Abkürzungen.xlsx. Bewusst nur die dort
 * gelisteten Kürzel — alle anderen bleiben als Kürzel stehen (Fallback). Der
 * Abgleich ist case-insensitiv (die Datei führt z. B. PRODL, die Daten ProdL).
 */
const VOLLWORT: Record<string, string> = {
  AV: "Arbeitsvorbereitung",
  AZU: "Azubi",
  BEM: "Bemusterung",
  CUT: "Cutter",
  EK: "Einkauf",
  ENG: "Engineering",
  FI: "Finanzbuchhaltung",
  HR: "Human Ressources",
  LOG: "Logistik",
  MON: "Montage",
  NÄH: "Näherei",
  PRODL: "Produktionsleitung",
  QM: "Qualitätsmanagement",
  QS: "Qualitätssicherung",
  SCM: "Schäumerei",
  TEP: "Teppich",
};

/** Vollwort zu einem Abteilungskürzel; unbekannte Kürzel geben sich selbst zurück. */
export function vollwort(kuerzel: string): string {
  return VOLLWORT[kuerzel.trim().toUpperCase()] ?? kuerzel;
}
