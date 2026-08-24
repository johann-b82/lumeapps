/**
 * Belegschafts-KPIs fürs HR-Dashboard (Geschlecht, Beschäftigungsart,
 * Eintritt neu/Bestand, Kopfzahl je Abteilung) — aggregiert aus Personio.
 */
import { apiClient } from "./apiClient";

export interface LabelWert {
  key: string;
  wert: number;
}
export interface AbteilungWert {
  name: string;
  wert: number;
}
export interface BelegschaftKpi {
  gesamt: number;
  geschlecht: LabelWert[];
  beschaeftigung: LabelWert[];
  eintritt: LabelWert[];
  abteilungen: AbteilungWert[];
}

export function fetchBelegschaftKpi(): Promise<BelegschaftKpi> {
  return apiClient<BelegschaftKpi>("/api/hr/belegschaft-kpi");
}
