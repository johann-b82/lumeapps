/**
 * Kompetenzen — Qualifikationsmatrix je Bereich.
 *
 * Die Matrix ist transponiert: Zeilen sind Qualifikationen, Spalten Personen.
 * Je Zelle ein Anforderungslevel (0–4) und ein Erfüllungsgrad (0–100 %).
 */
import { apiClient } from "./apiClient";

export const KOMPETENZ_BEREICHE = [
  "produktion",
  "verwaltung",
  "safety",
  "quality",
] as const;
export type KompetenzBereich = (typeof KOMPETENZ_BEREICHE)[number];

export interface MatrixUebersicht {
  id: number;
  bereich: KompetenzBereich;
  blatt: string;
  titel: string | null;
  stand: string | null;
  qualifikationen: number;
  personen: number;
  importiert_am: string;
}

export interface KompetenzPerson {
  id: number;
  name: string;
  /** Treffer in Personio; null bei Schreibfehler oder Platzhalterspalte. */
  employee_id: number | null;
  durchschnitt: number | null;
  /** Qualifikationen mit Anforderung, die noch nicht bei 100 % liegen. */
  luecken: number;
}

export interface Zelle {
  person_id: number;
  anforderungslevel: number | null;
  erfuellungsgrad: number | null;
}

export interface Qualifikation {
  id: number;
  nr: number | null;
  kategorie: string | null;
  bezeichnung: string;
  anzahl_mitarbeiter: number;
  durchschnitt: number | null;
  zellen: Zelle[];
}

export interface Matrix {
  id: number;
  bereich: KompetenzBereich;
  blatt: string;
  titel: string | null;
  stand: string | null;
  importiert_am: string;
  personen: KompetenzPerson[];
  qualifikationen: Qualifikation[];
}

export interface MatrixVorschau {
  blatt: string;
  titel: string | null;
  qualifikationen: number;
  personen: number;
  bewertungen: number;
  zugeordnet: number;
  nicht_zugeordnet: string[];
  platzhalter: number;
}

export interface KompetenzImportVorschau {
  dateiname: string;
  bereich: string;
  matrizen: MatrixVorschau[];
  warnungen: string[];
}

export function fetchMatrizen(): Promise<MatrixUebersicht[]> {
  return apiClient<MatrixUebersicht[]>("/api/hr/kompetenzen");
}

export function fetchMatrix(id: number): Promise<Matrix> {
  return apiClient<Matrix>(`/api/hr/kompetenzen/matrix/${id}`);
}

function upload(
  bereich: string,
  aktion: "preview" | "commit",
  file: File,
): Promise<KompetenzImportVorschau> {
  const body = new FormData();
  body.append("file", file);
  return apiClient<KompetenzImportVorschau>(
    `/api/hr/kompetenzen/${bereich}/import/${aktion}`,
    { method: "POST", body },
  );
}

export function kompetenzImportPreview(bereich: string, file: File) {
  return upload(bereich, "preview", file);
}

export function kompetenzImportCommit(bereich: string, file: File) {
  return upload(bereich, "commit", file);
}

/** Anforderungslevel und Erfüllungsgrad einer Zelle setzen (legt sie bei Bedarf an). */
export function setzeZelle(
  matrixId: number,
  eingabe: {
    qualifikation_id: number;
    person_id: number;
    anforderungslevel: number | null;
    erfuellungsgrad: number | null;
  },
): Promise<Zelle> {
  return apiClient<Zelle>(`/api/hr/kompetenzen/matrix/${matrixId}/zelle`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}

/** Spalte ergänzen. */
export function legePersonAn(
  matrixId: number,
  eingabe: { name: string; employee_id?: number | null },
): Promise<KompetenzPerson> {
  return apiClient<KompetenzPerson>(`/api/hr/kompetenzen/matrix/${matrixId}/person`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}

export function entfernePerson(matrixId: number, personId: number): Promise<void> {
  return apiClient<void>(
    `/api/hr/kompetenzen/matrix/${matrixId}/person/${personId}`,
    { method: "DELETE" },
  );
}

/** Zeile ergänzen. */
export function legeQualifikationAn(
  matrixId: number,
  eingabe: { bezeichnung: string; kategorie?: string | null; nr?: number | null },
): Promise<Qualifikation> {
  return apiClient<Qualifikation>(
    `/api/hr/kompetenzen/matrix/${matrixId}/qualifikation`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(eingabe),
    },
  );
}

export function entferneQualifikation(
  matrixId: number,
  qualifikationId: number,
): Promise<void> {
  return apiClient<void>(
    `/api/hr/kompetenzen/matrix/${matrixId}/qualifikation/${qualifikationId}`,
    { method: "DELETE" },
  );
}
