/**
 * Schulungsvorgang — persistiertes Formblatt 71 mit QR, Lebenszyklus, Scan-
 * Prüfung und zugeordneten Zertifikaten (v1.121). Spiegelt die Einarbeitungs-
 * vorgang-API; Prüf-Ergebnis-Typen werden von dort wiederverwendet.
 */
import { apiClient } from "./apiClient";
import { fetchBlob, openBlob } from "./download";
import type { PruefErgebnis, VorgangStatus } from "./einarbeitungApi";

/** Ein hochgeladenes Zertifikat/Nachweis, einer Schulungszeile zugeordnet. */
export interface SchulungZertifikat {
  id: number;
  schulung_bezeichnung: string | null;
  dateiname: string;
  hochgeladen_am: string;
}

/** Ein Schulungsvorgang (Formblatt 71). */
export interface SchulungVorgang {
  id: number;
  typ: "schulung";
  doc_uid: string;
  employee_id: number | null;
  mitarbeiter_name: string;
  funktion: string | null;
  status: VorgangStatus;
  erstellt_am: string;
  uebergeben_am: string | null;
  zurueck_am: string | null;
  geprueft_am: string | null;
  vollstaendig: boolean | null;
  kommentar: string | null;
  hat_scan: boolean;
  pruef_ergebnis: PruefErgebnis | null;
  zertifikate: SchulungZertifikat[];
}

export function fetchSchulungVorgaenge(): Promise<SchulungVorgang[]> {
  return apiClient<SchulungVorgang[]>("/api/hr/schulungen/dokumente");
}

/** Schulungsvorgang anlegen (Zeilen leitet der Server aus dem Soll-Plan ab). */
export function schulungVorgangAnlegen(employeeId: number): Promise<SchulungVorgang> {
  return apiClient<SchulungVorgang>("/api/hr/schulungen/dokument", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ employee_id: employeeId }),
  });
}

export function setzeSchulungStatus(id: number, status: VorgangStatus): Promise<SchulungVorgang> {
  return apiClient<SchulungVorgang>(`/api/hr/schulungen/dokument/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export function aktualisiereSchulungVorgang(
  id: number,
  eingabe: { kommentar?: string; vollstaendig?: boolean; bestaetigte_felder?: string[] },
): Promise<SchulungVorgang> {
  return apiClient<SchulungVorgang>(`/api/hr/schulungen/dokument/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}

export function scanSchulungHochladen(
  datei: File,
): Promise<{ dokument: SchulungVorgang; ergebnis: PruefErgebnis }> {
  const formular = new FormData();
  formular.append("datei", datei);
  return apiClient<{ dokument: SchulungVorgang; ergebnis: PruefErgebnis }>(
    "/api/hr/schulungen/scan",
    { method: "POST", body: formular },
  );
}

export async function oeffneSchulungPdf(id: number): Promise<void> {
  openBlob(await fetchBlob(`/api/hr/schulungen/dokument/${id}/pdf`));
}

export async function oeffneSchulungScan(id: number): Promise<void> {
  openBlob(await fetchBlob(`/api/hr/schulungen/dokument/${id}/scan`));
}

/** Zertifikat/Nachweis hochladen und optional einer Schulungszeile zuordnen. */
export function zertifikatHochladen(
  dokumentId: number,
  datei: File,
  schulungBezeichnung?: string,
): Promise<SchulungVorgang> {
  const formular = new FormData();
  formular.append("datei", datei);
  if (schulungBezeichnung) formular.append("schulung_bezeichnung", schulungBezeichnung);
  return apiClient<SchulungVorgang>(`/api/hr/schulungen/dokument/${dokumentId}/zertifikat`, {
    method: "POST",
    body: formular,
  });
}

export async function oeffneZertifikat(zertId: number): Promise<void> {
  openBlob(await fetchBlob(`/api/hr/schulungen/zertifikat/${zertId}/datei`));
}

export function zertifikatLoeschen(zertId: number): Promise<SchulungVorgang> {
  return apiClient<SchulungVorgang>(`/api/hr/schulungen/zertifikat/${zertId}`, {
    method: "DELETE",
  });
}
