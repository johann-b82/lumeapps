/**
 * Schulungs-Modul — API-Anbindung.
 *
 * Der Import folgt dem ATR-Muster: erst `preview` (schreibt nichts), dann
 * `commit` mit derselben Datei. Beide liefern dieselbe Struktur zurück, damit
 * die Oberfläche Vorschau und Ergebnis identisch darstellen kann.
 */
import { apiClient } from "./apiClient";

export interface NichtZugeordnet {
  personalnummer: string;
  mitarbeiter_name: string | null;
  anzahl_teilnahmen: number;
}

export interface SchulungImportVorschau {
  dateiname: string;
  schulungen_gesamt: number;
  schulungen_neu: number;
  teilnahmen_gesamt: number;
  teilnahmen_zugeordnet: number;
  /** Anzahl Schulungen je Bereich, z. B. { Produktion: 40 }. */
  bereiche: Record<string, number>;
  nicht_zugeordnet: NichtZugeordnet[];
  warnungen: string[];
}

export interface Schulung {
  id: number;
  bereich: string;
  name: string;
  turnus: string | null;
  /** Abgeleitete Periode; null bei "bei Bedarf" / Spannen — dann keine Fälligkeit. */
  turnus_monate: number | null;
  aktiv: boolean;
  teilnahmen: number;
}

function upload(pfad: string, file: File): Promise<SchulungImportVorschau> {
  const fd = new FormData();
  fd.append("file", file);
  return apiClient<SchulungImportVorschau>(pfad, { method: "POST", body: fd });
}

/** Datei analysieren, ohne etwas zu schreiben. */
export function schulungImportPreview(file: File): Promise<SchulungImportVorschau> {
  return upload("/api/hr/schulungen/import/preview", file);
}

/** Datei übernehmen (idempotent — erneuter Import aktualisiert). */
export function schulungImportCommit(file: File): Promise<SchulungImportVorschau> {
  return upload("/api/hr/schulungen/import/commit", file);
}

export function fetchSchulungen(): Promise<Schulung[]> {
  return apiClient<Schulung[]>("/api/hr/schulungen");
}

export interface Abteilung {
  abteilung: string;
  mitarbeiter: number;
  /** Führungskraft mit den meisten Unterstellten in dieser Abteilung. */
  vorgesetzter: string | null;
  unterstellte: number;
  /** Weitere Führungskräfte derselben Abteilung (häufig > 0). */
  weitere_vorgesetzte: number;
}

export function fetchAbteilungen(): Promise<Abteilung[]> {
  return apiClient<Abteilung[]>("/api/hr/schulungen/abteilungen");
}
