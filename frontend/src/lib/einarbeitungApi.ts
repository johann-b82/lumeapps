/**
 * Einarbeitung — Matrix je Abteilung und personalisierter Einarbeitungsbogen.
 *
 * App-gepflegt: die Inhalte werden in der Oberfläche angelegt, es gibt keinen
 * Excel-Import. Der Bogen entsteht auf Knopfdruck als PDF.
 */
import { apiClient } from "./apiClient";
import { fetchBlob, openBlob } from "./download";

export interface EinarbeitungInhalt {
  id: number;
  abteilung: string;
  ansprechpartner: string | null;
  inhalt: string;
  reihenfolge: number;
}

export function fetchEinarbeitungMatrix(): Promise<EinarbeitungInhalt[]> {
  return apiClient<EinarbeitungInhalt[]>("/api/hr/einarbeitung/matrix");
}

export function fetchEinarbeitungAbteilungen(): Promise<string[]> {
  return apiClient<string[]>("/api/hr/einarbeitung/abteilungen");
}

export function legeInhaltAn(eingabe: {
  abteilung: string;
  inhalt: string;
  ansprechpartner?: string | null;
}): Promise<EinarbeitungInhalt> {
  return apiClient<EinarbeitungInhalt>("/api/hr/einarbeitung/inhalt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}

export function aendereInhalt(
  id: number,
  eingabe: { abteilung?: string; inhalt?: string; ansprechpartner?: string | null },
): Promise<EinarbeitungInhalt> {
  return apiClient<EinarbeitungInhalt>(`/api/hr/einarbeitung/inhalt/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}

export function entferneInhalt(id: number): Promise<void> {
  return apiClient<void>(`/api/hr/einarbeitung/inhalt/${id}`, { method: "DELETE" });
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
