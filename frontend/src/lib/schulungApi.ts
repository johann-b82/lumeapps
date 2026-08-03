/**
 * Schulungs-Modul — API-Anbindung.
 *
 * Der Import folgt dem ATR-Muster: erst `preview` (schreibt nichts), dann
 * `commit` mit derselben Datei. Beide liefern dieselbe Struktur zurück, damit
 * die Oberfläche Vorschau und Ergebnis identisch darstellen kann.
 */
import { apiClient } from "./apiClient";
import { fetchBlob, openBlob } from "./download";

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
  /** Frist in Tagen nach Eintritt/Zuweisung; null = nicht definiert. */
  frist_tage: number | null;
  /** Verantwortlicher/Trainer; null = nicht gesetzt. */
  verantwortlicher: string | null;
  /** Schulungsbeschreibung; null = leer. */
  beschreibung: string | null;
  /** Anzahl hinterlegter Unterlagen. */
  anzahl_unterlagen: number;
  aktiv: boolean;
  teilnahmen: number;
}

/** Eine hochgeladene Schulungsunterlage. */
export interface Unterlage {
  id: number;
  dateiname: string;
  mime: string | null;
}

/** Setzt die Beschreibung einer Schulung; leer löscht sie (je Name geteilt). */
export function setzeBeschreibung(schulungId: number, beschreibung: string | null): Promise<void> {
  return apiClient<void>(`/api/hr/schulungen/${schulungId}/beschreibung`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ beschreibung }),
  });
}

export function fetchUnterlagen(schulungId: number): Promise<Unterlage[]> {
  return apiClient<Unterlage[]>(`/api/hr/schulungen/${schulungId}/unterlagen`);
}

export function ladeUnterlageHoch(schulungId: number, file: File): Promise<Unterlage> {
  const fd = new FormData();
  fd.append("file", file);
  return apiClient<Unterlage>(`/api/hr/schulungen/${schulungId}/unterlagen`, {
    method: "POST",
    body: fd,
  });
}

export function entferneUnterlage(unterlageId: number): Promise<void> {
  return apiClient<void>(`/api/hr/schulungen/unterlage/${unterlageId}`, { method: "DELETE" });
}

/** Lädt eine Unterlage herunter/öffnet sie. */
export async function ladeUnterlage(unterlageId: number, dateiname: string): Promise<void> {
  const blob = await fetchBlob(`/api/hr/schulungen/unterlage/${unterlageId}/download`);
  openBlob(blob, dateiname);
}

/** Setzt den Wiederholungs-Turnus (Monate) einer Schulung; null = bei Bedarf. */
export function setzeTurnus(schulungId: number, turnusMonate: number | null): Promise<void> {
  return apiClient<void>(`/api/hr/schulungen/${schulungId}/turnus`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ turnus_monate: turnusMonate }),
  });
}

/** Setzt die Frist (Tage nach Eintritt/Zuweisung) einer Schulung; null löscht sie. */
export function setzeFrist(schulungId: number, fristTage: number | null): Promise<void> {
  return apiClient<void>(`/api/hr/schulungen/${schulungId}/frist`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ frist_tage: fristTage }),
  });
}

/** Setzt den Verantwortlichen/Trainer einer Schulung; leer löscht ihn. */
export function setzeVerantwortlicher(
  schulungId: number,
  verantwortlicher: string | null,
): Promise<void> {
  return apiClient<void>(`/api/hr/schulungen/${schulungId}/verantwortlicher`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ verantwortlicher }),
  });
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
  /** "p:<personalnummer>" oder "e:<employee_id>" — siehe fetchMitarbeiterSchulungen. */
  schluessel: string;
  employee_id: number | null;
  personalnummer: string | null;
  name: string;
  abteilung: string | null;
  schulungen: number;
  ueberfaellig: number;
  bald_faellig: number;
  naechste_faelligkeit: string | null;
}

export interface MitarbeiterSchulung {
  /** Zeilen-ID, nötig zum Entfernen einer Einzelzuweisung. */
  teilnahme_id: number;
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
  /** Stabiler Schlüssel je Mitarbeiter ("p:<persnr>" / "e:<id>"). */
  schluessel: string;
  personalnummer: string | null;
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
  schluessel: string,
): Promise<MitarbeiterSchulung[]> {
  return apiClient<MitarbeiterSchulung[]>(
    `/api/hr/schulungen/mitarbeiter/${encodeURIComponent(schluessel)}`,
  );
}

export interface ZuweisbarerMitarbeiter {
  employee_id: number;
  personalnummer: string | null;
  name: string;
  abteilung: string | null;
}

/** Alle aktiven Personio-Mitarbeiter — auch ohne bisherige Schulung. */
export function fetchZuweisbare(): Promise<ZuweisbarerMitarbeiter[]> {
  return apiClient<ZuweisbarerMitarbeiter[]>("/api/hr/schulungen/zuweisbar");
}

export interface Zuweisung {
  teilnahme_id: number;
  employee_id: number;
  schulung_id: number;
  name: string;
  schulung: string;
}

/** Weist einer einzelnen Person eine einzelne Schulung zu (offen, ohne Datum). */
export function weiseSchulungZu(eingabe: {
  employee_id: number;
  schulung_id: number;
}): Promise<Zuweisung> {
  return apiClient<Zuweisung>("/api/hr/schulungen/zuweisen", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}

/** Nimmt eine Zuweisung zurück — nur solange kein Nachweis eingetragen ist. */
export function entferneZuweisung(teilnahmeId: number): Promise<void> {
  return apiClient<void>(`/api/hr/schulungen/zuweisung/${teilnahmeId}`, {
    method: "DELETE",
  });
}

/** Lädt den Schulungsnachweis (Formblatt 68) einer Schulung als PDF herunter. */
export async function ladeSchulungsprotokoll(
  schulungId: number,
  name: string,
): Promise<void> {
  const blob = await fetchBlob(`/api/hr/schulungen/${schulungId}/protokoll/pdf`);
  const heute = new Date();
  const stand = [
    heute.getFullYear(),
    String(heute.getMonth() + 1).padStart(2, "0"),
    String(heute.getDate()).padStart(2, "0"),
  ].join(".");
  openBlob(blob, `${stand}_${name.split(" ").join("_")}_Schulungsnachweis.pdf`);
}
