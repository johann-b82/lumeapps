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

// --- Schulungsbericht-Upload (PDF) → Stand fortschreiben ---------------------

export type BerichtMitarbeiterStatus = "ok" | "nicht_gefunden" | "mehrdeutig";

export interface BerichtZeile {
  mitarbeiter_name: string;
  schulung_name: string;
  datum: string | null;
  mitarbeiter_status: BerichtMitarbeiterStatus;
  /** Aufgelöste Personio-ID (null, wenn nicht/mehrdeutig) — Vorauswahl im Dropdown. */
  employee_id: number | null;
  /** Aufgelöster Personio-Name (null, wenn nicht/mehrdeutig gefunden). */
  matched_mitarbeiter: string | null;
  schulung_im_katalog: boolean;
  /** True = Mitarbeiter + Datum vorhanden (wäre übernehmbar). */
  uebernehmbar: boolean;
}

export interface BerichtVorschau {
  format: string;
  format_label: string;
  gesamt: number;
  uebernehmbar: number;
  ohne_mitarbeiter: number;
  ohne_datum: number;
  neue_schulungen: number;
  zeilen: BerichtZeile[];
}

/** Schulungsbericht-PDF (Fbl. 68/71) auswerten — nichts schreiben. */
export function berichtPreview(file: File): Promise<BerichtVorschau> {
  const fd = new FormData();
  fd.append("file", file);
  return apiClient<BerichtVorschau>("/api/hr/schulungen/bericht/preview", {
    method: "POST",
    body: fd,
  });
}

/** Eine bearbeitete Zeile zur Übernahme. */
export interface BerichtCommitZeile {
  employee_id: number;
  schulung_name: string;
  datum: string;
}

export interface BerichtCommitErgebnis {
  eingetragen: number;
  angelegte_schulungen: number;
}

/** Bearbeitete Berichtszeilen übernehmen (Durchführung setzen, fehlende Schulungen anlegen). */
export function berichtCommit(
  zeilen: BerichtCommitZeile[],
): Promise<BerichtCommitErgebnis> {
  return apiClient<BerichtCommitErgebnis>("/api/hr/schulungen/bericht/commit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ zeilen }),
  });
}

export function fetchSchulungen(): Promise<Schulung[]> {
  return apiClient<Schulung[]>("/api/hr/schulungen");
}

/** Neue Schulung im Katalog anlegen (Name + Bereich; Rest danach pflegbar). */
export function erstelleSchulung(eingabe: {
  name: string;
  bereich: string;
}): Promise<Schulung> {
  return apiClient<Schulung>("/api/hr/schulungen", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}

/** Schulung entfernen (inkl. aller gleichnamigen Katalogzeilen + Teilnahmen). */
export function entferneSchulung(schulungId: number): Promise<void> {
  return apiClient<void>(`/api/hr/schulungen/${schulungId}`, { method: "DELETE" });
}

export interface Abteilung {
  abteilung: string;
  mitarbeiter: number;
  /** Alle Vorgesetzten dieser Abteilung, absteigend nach Unterstellten. */
  vorgesetzte: string[];
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
  /** Personio-Standort (z. B. "Hamburg"); null bei Externen. */
  office: string | null;
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

// --- Schulungsmatrix: wer hat welche Schulung absolviert --------------------

export interface MatrixSchulung {
  id: number;
  name: string;
  bereich: string;
}

export interface MatrixZelle {
  schulung_id: number;
  /** Durchführungsdatum; null = zugewiesen, noch offen. */
  datum: string | null;
  status: SchulungStatus;
  /** True = zugewiesen, noch nicht absolviert. */
  offen: boolean;
}

export interface MatrixZeile {
  schluessel: string;
  name: string;
  abteilung: string | null;
  office: string | null;
  zellen: MatrixZelle[];
}

export interface SchulungsMatrix {
  /** Absolvierte Schulungen = Spalten (nach Bereich, Name sortiert). */
  schulungen: MatrixSchulung[];
  /** Mitarbeiter = Zeilen (nach Name sortiert). */
  zeilen: MatrixZeile[];
}

export function fetchSchulungsMatrix(): Promise<SchulungsMatrix> {
  return apiClient<SchulungsMatrix>("/api/hr/schulungen/matrix");
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
  /** Personio-Standort (z. B. "Hamburg"); null bei Externen. */
  office: string | null;
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

/** Setzt das Durchführungsdatum einer Teilnahme; null setzt sie auf "offen" zurück. */
export function setzeDurchgefuehrt(teilnahmeId: number, datum: string | null): Promise<void> {
  return apiClient<void>(`/api/hr/schulungen/teilnahme/${teilnahmeId}/durchgefuehrt`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ datum }),
  });
}

/** Trägt eine Schulung für mehrere Mitarbeiter zum selben Datum als durchgeführt ein. */
export function sammelDurchgefuehrt(eingabe: {
  schulung_id: number;
  datum: string;
  employee_ids: number[];
}): Promise<{ eingetragen: number }> {
  return apiClient<{ eingetragen: number }>("/api/hr/schulungen/durchgefuehrt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
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
