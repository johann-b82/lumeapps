/**
 * Onboarding — neue Eintritte und ihr abgeleiteter Schulungsplan.
 *
 * Der Plan entsteht aus der Anforderungsmatrix: grobe Ebene über die
 * Personio-Abteilung, feine Ebene über die Zuordnung Position → Kürzel.
 */
import { apiClient } from "./apiClient";

export interface Eintritt {
  employee_id: number;
  personalnummer: string | null;
  name: string;
  position: string | null;
  abteilung: string | null;
  hire_date: string | null;
  /** Negativ = liegt n Tage zurück, positiv = beginnt in n Tagen. */
  tage_bis_eintritt: number | null;
  soll_gesamt: number;
  fehlend: number;
  /** Position hat keine Zuordnung → feine Matrix-Ebene greift nicht. */
  kuerzel_fehlt: boolean;
}

export interface SollSchulung {
  schulung_id: number;
  bereich: string;
  name: string;
  turnus: string | null;
  /** "personio" (grobe Ebene) oder "kuerzel" (feine Ebene). */
  quelle: string;
  abteilung: string;
  vorhanden: boolean;
}

export interface Schulungsplan {
  employee_id: number;
  personalnummer: string | null;
  name: string;
  position: string | null;
  abteilung: string | null;
  abteilung_kuerzel: string | null;
  kuerzel_fehlt: boolean;
  soll: SollSchulung[];
  fehlend: number;
}

export interface Rolle {
  id: number;
  position: string;
  abteilung_kuerzel: string;
}

export function fetchEintritte(): Promise<Eintritt[]> {
  return apiClient<Eintritt[]>("/api/hr/onboarding/eintritte");
}

export function fetchPlan(employeeId: number): Promise<Schulungsplan> {
  return apiClient<Schulungsplan>(`/api/hr/onboarding/plan/${employeeId}`);
}

/** Legt die fehlenden Pflichtschulungen als offene Zeilen an (idempotent). */
export function erzeugePlan(employeeId: number): Promise<Schulungsplan> {
  return apiClient<Schulungsplan>(`/api/hr/onboarding/plan/${employeeId}`, {
    method: "POST",
  });
}

export function fetchRollen(): Promise<Rolle[]> {
  return apiClient<Rolle[]>("/api/hr/onboarding/rollen");
}

export function setzeRolle(eingabe: {
  position: string;
  abteilung_kuerzel: string;
}): Promise<Rolle> {
  return apiClient<Rolle>("/api/hr/onboarding/rollen", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}
