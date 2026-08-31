/**
 * Arbeitszeugnisse — Stammdaten, Bewertung, KI-Text und DOCX/PDF.
 *
 * Personen kommen aus Personio bzw. der Externe-Liste (negative ID). Der
 * Zeugnistext wird serverseitig von Claude generiert (datensparsam: Name/
 * Geburtsdatum/Personalnummer verlassen den Server nicht) und ist danach hier
 * editierbar.
 */
import { apiClient } from "./apiClient";
import { fetchBlob, openBlob } from "./download";

export type ZeugnisArt =
  | "qualifiziert"
  | "einfach"
  | "zwischenzeugnis"
  | "ausbildungszeugnis"
  | "praktikumszeugnis";

/** Bewertungsdimensionen (Schlüssel = Backend, Label über i18n zeugnisse.dim.*). */
export const ZEUGNIS_DIMENSIONEN = [
  "fachwissen",
  "auffassungsgabe",
  "arbeitsweise",
  "belastbarkeit",
  "arbeitserfolg",
  "sozialverhalten",
  "fuehrung",
] as const;

/** Abschnitte des generierten Textes (Reihenfolge = Anzeige). */
export const ZEUGNIS_ABSCHNITTE = [
  "einleitung",
  "taetigkeitsbeschreibung",
  "leistungsbeurteilung",
  "sozialverhalten",
  "schlussformel",
] as const;

export interface Person {
  /** Positiv = Personio-ID; negativ = -onboarding_extern.id. */
  employee_id: number;
  name: string;
  abteilung: string | null;
  position: string | null;
  status: string | null;
}

export interface ZeugnisListItem {
  id: number;
  name: string;
  taetigkeit: string | null;
  art: ZeugnisArt;
  status: string;
  schlussnote: number | null;
  aktualisiert_am: string;
}

export interface ZeugnisDetail {
  id: number;
  employee_id: number | null;
  extern_id: number | null;
  name: string;
  geschlecht: string | null;
  geburtsdatum: string | null;
  personalnummer: string | null;
  abteilung: string | null;
  taetigkeit: string | null;
  eintritt: string | null;
  austritt: string | null;
  art: ZeugnisArt;
  anlass: string | null;
  fuehrungskraft: boolean;
  ausstellungsdatum: string | null;
  taetigkeit_stichpunkte: string | null;
  besondere_kompetenzen: string | null;
  besondere_erfolge: string | null;
  schlussnote: number | null;
  bewertungen: Record<string, number>;
  abschnitte: Record<string, string> | null;
  status: string;
}

export interface Aussteller {
  firma: string;
  standort: string | null;
  unterzeichner1_name: string | null;
  unterzeichner1_titel: string | null;
  unterzeichner2_name: string | null;
  unterzeichner2_titel: string | null;
}

const BASE = "/api/hr/zeugnisse";

export function fetchPersonen(): Promise<Person[]> {
  return apiClient<Person[]>(`${BASE}/personen`);
}

export function fetchZeugnisse(): Promise<ZeugnisListItem[]> {
  return apiClient<ZeugnisListItem[]>(BASE);
}

export function fetchZeugnis(id: number): Promise<ZeugnisDetail> {
  return apiClient<ZeugnisDetail>(`${BASE}/${id}`);
}

export function createZeugnis(employee_id: number, art: ZeugnisArt): Promise<ZeugnisDetail> {
  return apiClient<ZeugnisDetail>(BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ employee_id, art }),
  });
}

export type ZeugnisPatch = Partial<
  Pick<
    ZeugnisDetail,
    | "name" | "geschlecht" | "geburtsdatum" | "personalnummer" | "abteilung"
    | "taetigkeit" | "eintritt" | "austritt" | "art" | "anlass" | "fuehrungskraft"
    | "ausstellungsdatum" | "taetigkeit_stichpunkte" | "besondere_kompetenzen"
    | "besondere_erfolge" | "status" | "bewertungen" | "abschnitte"
  >
>;

export function updateZeugnis(id: number, patch: ZeugnisPatch): Promise<ZeugnisDetail> {
  return apiClient<ZeugnisDetail>(`${BASE}/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

export function deleteZeugnis(id: number): Promise<void> {
  return apiClient<void>(`${BASE}/${id}`, { method: "DELETE" });
}

export function generateZeugnis(id: number): Promise<ZeugnisDetail> {
  return apiClient<ZeugnisDetail>(`${BASE}/${id}/generate`, { method: "POST" });
}

/** Nur einen einzelnen Abschnitt gezielt neu erzeugen (KI). */
export function generateAbschnitt(id: number, abschnitt: string): Promise<ZeugnisDetail> {
  return apiClient<ZeugnisDetail>(`${BASE}/${id}/generate/${abschnitt}`, { method: "POST" });
}

/** Gesamtes Zeugnis deterministisch aus Textbausteinen erzeugen (ohne KI). */
export function baukastenZeugnis(id: number): Promise<ZeugnisDetail> {
  return apiClient<ZeugnisDetail>(`${BASE}/${id}/baukasten`, { method: "POST" });
}

/** Einen einzelnen Abschnitt aus Textbausteinen erzeugen (ohne KI). */
export function baukastenAbschnitt(id: number, abschnitt: string): Promise<ZeugnisDetail> {
  return apiClient<ZeugnisDetail>(`${BASE}/${id}/baukasten/${abschnitt}`, { method: "POST" });
}

export function fetchAussteller(): Promise<Aussteller | null> {
  return apiClient<Aussteller | null>(`${BASE}/aussteller`);
}

export function saveAussteller(a: Aussteller): Promise<Aussteller> {
  return apiClient<Aussteller>(`${BASE}/aussteller`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(a),
  });
}

// --- Bewertungs-Vorlagen (Profile) ---
export interface Vorlage {
  id: number;
  name: string;
  noten: Record<string, number>;
}
export function fetchVorlagen(): Promise<Vorlage[]> {
  return apiClient<Vorlage[]>(`${BASE}/vorlagen`);
}
export function createVorlage(name: string, noten: Record<string, number>): Promise<Vorlage> {
  return apiClient<Vorlage>(`${BASE}/vorlagen`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, noten }),
  });
}
export function deleteVorlage(id: number): Promise<void> {
  return apiClient<void>(`${BASE}/vorlagen/${id}`, { method: "DELETE" });
}

// --- Textbausteine (editierbare Standardformulierungen je Dimension × Note) ---
export interface Baustein {
  dimension: string;
  note: number;
  text: string;
}
export function fetchBausteine(): Promise<Baustein[]> {
  return apiClient<Baustein[]>(`${BASE}/bausteine`);
}
export function saveBausteine(bausteine: Baustein[]): Promise<Baustein[]> {
  return apiClient<Baustein[]>(`${BASE}/bausteine`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bausteine }),
  });
}

export async function downloadDocx(id: number, name: string): Promise<void> {
  const blob = await fetchBlob(`${BASE}/${id}/docx`);
  openBlob(blob, `Arbeitszeugnis_${name.replace(/\s+/g, "_")}.docx`);
}

export async function downloadPdf(id: number, name: string): Promise<void> {
  const blob = await fetchBlob(`${BASE}/${id}/pdf`);
  openBlob(blob, `Arbeitszeugnis_${name.replace(/\s+/g, "_")}.pdf`);
}
