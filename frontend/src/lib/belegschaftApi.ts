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
  /** Stichtag (ISO) — null bei der aktuellen (statusbasierten) Ansicht;
   *  in älteren Newsletter-Snapshots evtl. gar nicht vorhanden. */
  stichtag?: string | null;
}

export interface BelegschaftMeta {
  min_jahr: number;
  aktuelles_jahr: number;
}

/** Belegschafts-KPIs. Ohne jahr → aktuelle Belegschaft; mit jahr(+quartal) →
 *  Stichtag am Periodenende. */
export function fetchBelegschaftKpi(
  jahr?: number,
  quartal?: number,
): Promise<BelegschaftKpi> {
  const p = new URLSearchParams();
  if (jahr != null) p.set("jahr", String(jahr));
  if (quartal != null) p.set("quartal", String(quartal));
  const qs = p.toString();
  return apiClient<BelegschaftKpi>(`/api/hr/belegschaft-kpi${qs ? `?${qs}` : ""}`);
}

export function fetchBelegschaftMeta(): Promise<BelegschaftMeta> {
  return apiClient<BelegschaftMeta>("/api/hr/belegschaft-kpi/meta");
}
