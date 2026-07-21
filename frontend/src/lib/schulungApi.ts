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

/** "ueberfaellig" | "bald" | "ok" | "ohne_frist" */
export type SchulungStatus = "ueberfaellig" | "bald" | "ok" | "ohne_frist";

export interface MitarbeiterZeile {
  employee_id: number | null;
  personalnummer: string;
  name: string;
  abteilung: string | null;
  schulungen: number;
  ueberfaellig: number;
  bald_faellig: number;
  naechste_faelligkeit: string | null;
}

export interface MitarbeiterSchulung {
  schulung_id: number;
  bereich: string;
  name: string;
  turnus: string | null;
  initial_datum: string | null;
  aktuell_datum: string | null;
  naechste_faellig: string | null;
  naechste_faellig_am: string | null;
  status: SchulungStatus;
}

/** Feine Excel-Kürzel (NÄH, WVK …) bzw. grobe Personio-Abteilungen. */
export type PflichtEbene = "kuerzel" | "personio";

export interface PflichtMatrix {
  ebene: PflichtEbene;
  abteilungen: string[];
  /** Gesetzte Häkchen als "<schulung_id>:<abteilung>". */
  regeln: string[];
}

export function fetchPflichtMatrix(ebene: PflichtEbene): Promise<PflichtMatrix> {
  return apiClient<PflichtMatrix>(`/api/hr/schulungen/pflicht/${ebene}`);
}

export function setzePflicht(eingabe: {
  schulung_id: number;
  ebene: PflichtEbene;
  abteilung: string;
  pflicht: boolean;
}): Promise<void> {
  return apiClient<void>("/api/hr/schulungen/pflicht", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}

export interface OffeneSchulung {
  personalnummer: string;
  mitarbeiter_name: string;
  abteilung: string | null;
  abteilung_kuerzel: string | null;
  bereich: string;
  schulung: string;
  turnus: string | null;
  aktuell_datum: string | null;
  faellig_am: string;
  /** Negativ = überfällig seit n Tagen, positiv = fällig in n Tagen. */
  tage: number;
  status: SchulungStatus;
}

/** Überfällig oder in den nächsten 3 Monaten fällig, dringendstes zuerst. */
export function fetchOffeneSchulungen(): Promise<OffeneSchulung[]> {
  return apiClient<OffeneSchulung[]>("/api/hr/schulungen/offen");
}

export function fetchMitarbeiter(): Promise<MitarbeiterZeile[]> {
  return apiClient<MitarbeiterZeile[]>("/api/hr/schulungen/mitarbeiter");
}

export function fetchMitarbeiterSchulungen(
  personalnummer: string,
): Promise<MitarbeiterSchulung[]> {
  return apiClient<MitarbeiterSchulung[]>(
    `/api/hr/schulungen/mitarbeiter/${encodeURIComponent(personalnummer)}`,
  );
}
