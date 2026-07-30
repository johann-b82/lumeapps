/**
 * Einarbeitung — Matrix je Abteilung und personalisierter Einarbeitungsbogen.
 *
 * App-gepflegt: die Inhalte werden in der Oberfläche angelegt, es gibt keinen
 * Excel-Import. Der Bogen entsteht auf Knopfdruck als PDF.
 */
import { apiClient } from "./apiClient";
import { fetchBlob, openBlob } from "./download";

/** Eine Einarbeitung im Katalog (mit Ansprechpartner, abteilungsunabhängig). */
export interface EinarbeitungKatalog {
  id: number;
  inhalt: string;
  ansprechpartner: string | null;
  reihenfolge: number;
}

/** Achse + gesetzte Häkchen der Einarbeitungs-Matrix. */
export interface EinarbeitungPflicht {
  abteilungen: string[];
  /** "<einarbeitung_id>:<abteilung>" */
  regeln: string[];
}

export function fetchEinarbeitungKatalog(): Promise<EinarbeitungKatalog[]> {
  return apiClient<EinarbeitungKatalog[]>("/api/hr/einarbeitung/katalog");
}

export function fetchEinarbeitungAbteilungen(): Promise<string[]> {
  return apiClient<string[]>("/api/hr/einarbeitung/abteilungen");
}

export function legeKatalogAn(eingabe: {
  inhalt: string;
  ansprechpartner?: string | null;
}): Promise<EinarbeitungKatalog> {
  return apiClient<EinarbeitungKatalog>("/api/hr/einarbeitung/katalog", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}

export function aendereKatalog(
  id: number,
  eingabe: { inhalt?: string; ansprechpartner?: string | null },
): Promise<EinarbeitungKatalog> {
  return apiClient<EinarbeitungKatalog>(`/api/hr/einarbeitung/katalog/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}

export function entferneKatalog(id: number): Promise<void> {
  return apiClient<void>(`/api/hr/einarbeitung/katalog/${id}`, { method: "DELETE" });
}

export function fetchEinarbeitungPflicht(): Promise<EinarbeitungPflicht> {
  return apiClient<EinarbeitungPflicht>("/api/hr/einarbeitung/pflicht");
}

export function setzeEinarbeitungPflicht(eingabe: {
  einarbeitung_id: number;
  abteilung: string;
  pflicht: boolean;
}): Promise<void> {
  return apiClient<void>("/api/hr/einarbeitung/pflicht", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}

/** Lädt den Einarbeitungsbogen als PDF herunter (für die gewählten Abteilungen). */
export async function ladeEinarbeitungsplan(
  employeeId: number,
  name: string,
  abteilungen: string[],
): Promise<void> {
  const q = abteilungen
    .map((a) => `abteilungen=${encodeURIComponent(a)}`)
    .join("&");
  const url = `/api/hr/einarbeitung/plan/${employeeId}/pdf${q ? `?${q}` : ""}`;
  const blob = await fetchBlob(url);
  const heute = new Date();
  const stand = [
    heute.getFullYear(),
    String(heute.getMonth() + 1).padStart(2, "0"),
    String(heute.getDate()).padStart(2, "0"),
  ].join(".");
  openBlob(blob, `${stand}_${name.split(" ").join("_")}_Einarbeitungsplan.pdf`);
}

/** Aktive Personio-Mitarbeiter als Vorschläge für den Ansprechpartner. */
export function fetchAnsprechpartner(): Promise<string[]> {
  return apiClient<string[]>("/api/hr/einarbeitung/ansprechpartner");
}
