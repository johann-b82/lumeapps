/**
 * Abteilungskürzel → Vollwort, plus in der Anforderungsmatrix ausgeblendete Kürzel.
 *
 * Quelle: vom Betrieb gelieferte Abkürzungen.xlsx (ergänzt um VK/WVK/ZU). Bewusst
 * nur die gelisteten Kürzel bekommen ein Vollwort — alle anderen bleiben als
 * Kürzel stehen. Der Abgleich ist case- und leerzeichen-insensitiv (die Datei
 * führt z. B. PRODL, die Daten ProdL; „AV (CS)" vs. „AV(CS)").
 */
function norm(kuerzel: string): string {
  return kuerzel.trim().toUpperCase().replace(/\s+/g, "");
}

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
  VK: "Verpackung",
  WVK: "Wandverkleidung",
  ZU: "Zuschnitt",
};

/** In der Anforderungsmatrix nicht als Spalte anzuzeigende Kürzel (normalisiert). */
const AUSGEBLENDET = new Set(["AV(CS)", "MON(CS)", "PRODL(CS)", "REI"]);

/** Vollwort zu einem Abteilungskürzel; unbekannte Kürzel geben sich selbst zurück. */
export function vollwort(kuerzel: string): string {
  return VOLLWORT[norm(kuerzel)] ?? kuerzel;
}

/** Ob ein Kürzel in der Anforderungsmatrix ausgeblendet werden soll. */
export function abteilungAusgeblendet(kuerzel: string): boolean {
  return AUSGEBLENDET.has(norm(kuerzel));
}
