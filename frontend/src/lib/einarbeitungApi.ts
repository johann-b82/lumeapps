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
  /** Bereich der Einarbeitung — erscheint im PDF als „Abteilung". */
  bereich: string | null;
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
  bereich?: string | null;
}): Promise<EinarbeitungKatalog> {
  return apiClient<EinarbeitungKatalog>("/api/hr/einarbeitung/katalog", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}

export function aendereKatalog(
  id: number,
  eingabe: { inhalt?: string; ansprechpartner?: string | null; bereich?: string | null },
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

// ---------------------------------------------------------------------------
// Vorgang: persistiertes Formular mit QR, Lebenszyklus (4 Zeitstempel) und
// Scan-Upload mit halbautomatischer Prüfung (v1.107).
// ---------------------------------------------------------------------------

/** Ein geprüftes Pflichtfeld aus der Scan-Auswertung. */
export interface PruefFeld {
  key: string;
  label: string;
  erkannt: boolean;
}

/** Ergebnis der halbautomatischen Scan-Prüfung. */
export interface PruefErgebnis {
  qr_ok: boolean;
  doc_uid?: string | null;
  felder: PruefFeld[];
  vollstaendig: boolean;
  fehlend: string[];
  /** Bei qr_ok=false: warum (kein_qr / unbekannt). */
  grund?: string;
}

export type VorgangStatus = "erstellt" | "uebergeben" | "zurueck" | "geprueft";

/** Ein Einarbeitungs-Vorgang (persistiertes Formular + Lebenszyklus). */
export interface Vorgang {
  id: number;
  doc_uid: string;
  employee_id: number | null;
  mitarbeiter_name: string;
  stelle: string | null;
  beginn: string | null;
  abteilungen: string[] | null;
  status: VorgangStatus;
  erstellt_am: string;
  uebergeben_am: string | null;
  zurueck_am: string | null;
  geprueft_am: string | null;
  vollstaendig: boolean | null;
  kommentar: string | null;
  hat_scan: boolean;
  pruef_ergebnis: PruefErgebnis | null;
}

export function fetchVorgaenge(): Promise<Vorgang[]> {
  return apiClient<Vorgang[]>("/api/hr/einarbeitung/dokumente");
}

/** Vorgang anlegen: erzeugt das PDF mit QR/Passermarken und persistiert ihn. */
export function vorgangAnlegen(employeeId: number, abteilungen: string[]): Promise<Vorgang> {
  return apiClient<Vorgang>("/api/hr/einarbeitung/dokument", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ employee_id: employeeId, abteilungen }),
  });
}

/** Lebenszyklus voranschieben (setzt Status + zugehörigen Zeitstempel). */
export function setzeVorgangStatus(id: number, status: VorgangStatus): Promise<Vorgang> {
  return apiClient<Vorgang>(`/api/hr/einarbeitung/dokument/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

/** Kommentar hinterlegen bzw. Vollständigkeit manuell überstimmen. */
export function aktualisiereVorgang(
  id: number,
  eingabe: { kommentar?: string; vollstaendig?: boolean },
): Promise<Vorgang> {
  return apiClient<Vorgang>(`/api/hr/einarbeitung/dokument/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}

/** Ausgefüllten/eingescannten Bogen hochladen → QR-Zuordnung + Prüfung. */
export function scanHochladen(
  datei: File,
): Promise<{ dokument: Vorgang; ergebnis: PruefErgebnis }> {
  const formular = new FormData();
  formular.append("datei", datei);
  return apiClient<{ dokument: Vorgang; ergebnis: PruefErgebnis }>(
    "/api/hr/einarbeitung/scan",
    { method: "POST", body: formular },
  );
}

/** Das hinterlegte Blanko-PDF eines Vorgangs im neuen Tab öffnen. */
export async function oeffneVorgangPdf(id: number): Promise<void> {
  const blob = await fetchBlob(`/api/hr/einarbeitung/dokument/${id}/pdf`);
  openBlob(blob);
}
