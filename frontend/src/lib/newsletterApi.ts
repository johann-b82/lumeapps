/**
 * Newsletter — vierteljährliche Ausgabe mit sechs festen Rubriken.
 *
 * Lesen (veröffentlichte Ausgaben) ist viewer-freigegeben; Redaktion (Anlegen/
 * Bearbeiten/Veröffentlichen) ist admin-only. Inhalt je Eintrag ist Markdown
 * (react-markdown), plus optional ein Bild.
 */
import { apiClient } from "./apiClient";
import type { BelegschaftKpi } from "./belegschaftApi";

export const NEWSLETTER_RUBRIKEN = [
  "arash",
  "aschkan",
  "intern",
  "rueckblick",
  "menschen",
  "neuigkeiten",
] as const;
export type Rubrik = (typeof NEWSLETTER_RUBRIKEN)[number];

export interface AusgabeListItem {
  id: number;
  jahr: number;
  quartal: number;
  titel: string | null;
  status: "entwurf" | "veroeffentlicht";
}

export interface EintragBild {
  id: number;
  reihenfolge: number;
  /** Zellen-Spanne im 4-Spalten-Raster. */
  spalten: number;
  zeilen: number;
}

export interface Eintrag {
  id: number;
  rubrik: Rubrik;
  untertitel: string;
  inhalt_md: string;
  reihenfolge: number;
  hat_bild: boolean;
  /** Puzzle-Bilder in Reihenfolge. */
  bilder: EintragBild[];
}

export interface NeuerMitarbeiter {
  name: string;
  abteilung: string | null;
  position: string | null;
}

export interface AusgabeDetail extends AusgabeListItem {
  eintraege: Eintrag[];
  /** Eingefrorener KPI-Stand für den „ACM KPIs"-Block; null = ohne. */
  kpi_snapshot: BelegschaftKpi | null;
  /** Neuzugänge im Quartal (live aus Personio) — Rubrik „Menschen". */
  neue_mitarbeiter: NeuerMitarbeiter[];
  /** Block-Reihenfolge (Rubrik-Schlüssel); null = Standard. */
  block_reihenfolge: string[] | null;
  /** Überschriebene Abschnitts-Titel {block_key: titel}; null/fehlend = Standard. */
  rubrik_titel: Record<string, string> | null;
  /** Vollflächiges Titel- bzw. Rückseitenbild hinterlegt? */
  hat_cover: boolean;
  hat_rueck: boolean;
}

const BASE = "/api/newsletter";

/** Bild-URL eines Eintrags (mit `t`, um Cache nach Neu-Upload zu umgehen). */
export function bildUrl(eintragId: number, bust?: number): string {
  return `${BASE}/eintrag/${eintragId}/bild${bust ? `?t=${bust}` : ""}`;
}

/** URL eines Puzzle-Bildes. */
export function eintragBildUrl(bildId: number): string {
  return `${BASE}/eintrag-bild/${bildId}`;
}

/** URL des vollflächigen Titelbilds einer Ausgabe. */
export function coverUrl(ausgabeId: number, bust?: number): string {
  return `${BASE}/${ausgabeId}/cover${bust ? `?t=${bust}` : ""}`;
}

/** URL des vollflächigen Rückseitenbilds einer Ausgabe. */
export function rueckUrl(ausgabeId: number, bust?: number): string {
  return `${BASE}/${ausgabeId}/rueckseite${bust ? `?t=${bust}` : ""}`;
}

// --- Viewer: veröffentlichte Ausgaben ---
export function fetchAusgaben(): Promise<AusgabeListItem[]> {
  return apiClient<AusgabeListItem[]>(BASE);
}
export function fetchAusgabe(id: number): Promise<AusgabeDetail> {
  return apiClient<AusgabeDetail>(`${BASE}/${id}`);
}

// --- Admin: Redaktion ---
export function fetchAdminAusgaben(): Promise<AusgabeListItem[]> {
  return apiClient<AusgabeListItem[]>(`${BASE}/admin`);
}
export function fetchAdminAusgabe(id: number): Promise<AusgabeDetail> {
  return apiClient<AusgabeDetail>(`${BASE}/admin/${id}`);
}
export function createAusgabe(eingabe: {
  jahr: number;
  quartal: number;
  titel?: string;
}): Promise<AusgabeDetail> {
  return apiClient<AusgabeDetail>(BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}
export function updateAusgabe(
  id: number,
  patch: {
    titel?: string | null;
    status?: "entwurf" | "veroeffentlicht";
    block_reihenfolge?: string[];
    rubrik_titel?: Record<string, string>;
  },
): Promise<AusgabeDetail> {
  return apiClient<AusgabeDetail>(`${BASE}/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}
export function deleteAusgabe(id: number): Promise<void> {
  return apiClient<void>(`${BASE}/${id}`, { method: "DELETE" });
}
export function addEintrag(
  ausgabeId: number,
  eingabe: { rubrik: Rubrik; untertitel: string; inhalt_md?: string },
): Promise<Eintrag> {
  return apiClient<Eintrag>(`${BASE}/${ausgabeId}/eintrag`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}
export function updateEintrag(
  id: number,
  patch: Partial<Pick<Eintrag, "rubrik" | "untertitel" | "inhalt_md" | "reihenfolge">>,
): Promise<Eintrag> {
  return apiClient<Eintrag>(`${BASE}/eintrag/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}
export function deleteEintrag(id: number): Promise<void> {
  return apiClient<void>(`${BASE}/eintrag/${id}`, { method: "DELETE" });
}
export function uploadBild(eintragId: number, datei: File): Promise<Eintrag> {
  const fd = new FormData();
  fd.append("datei", datei);
  // Kein Content-Type setzen → Browser schreibt die multipart-boundary.
  return apiClient<Eintrag>(`${BASE}/eintrag/${eintragId}/bild`, { method: "PUT", body: fd });
}
export function deleteBild(eintragId: number): Promise<void> {
  return apiClient<void>(`${BASE}/eintrag/${eintragId}/bild`, { method: "DELETE" });
}

// --- Puzzle-Bilder (mehrere je Eintrag) ---
export function uploadEintragBild(eintragId: number, datei: File): Promise<Eintrag> {
  const fd = new FormData();
  fd.append("datei", datei);
  return apiClient<Eintrag>(`${BASE}/eintrag/${eintragId}/bilder`, { method: "POST", body: fd });
}
export function deleteEintragBild(bildId: number): Promise<void> {
  return apiClient<void>(`${BASE}/eintrag-bild/${bildId}`, { method: "DELETE" });
}
export function updateEintragBildLayout(
  bildId: number,
  patch: { spalten?: number; zeilen?: number },
): Promise<EintragBild> {
  return apiClient<EintragBild>(`${BASE}/eintrag-bild/${bildId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}
export function reorderEintragBilder(eintragId: number, ids: number[]): Promise<Eintrag> {
  return apiClient<Eintrag>(`${BASE}/eintrag/${eintragId}/bilder/anordnung`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
}

/** Aktuelle Belegschafts-KPIs als Snapshot in die Ausgabe einfrieren. */
export function insertKpi(ausgabeId: number): Promise<AusgabeDetail> {
  return apiClient<AusgabeDetail>(`${BASE}/${ausgabeId}/kpi`, { method: "POST" });
}
export function removeKpi(ausgabeId: number): Promise<AusgabeDetail> {
  return apiClient<AusgabeDetail>(`${BASE}/${ausgabeId}/kpi`, { method: "DELETE" });
}

// --- Admin: Titel-/Rückseitenbild (vollflächig) ---
function uploadAusgabeBild(pfad: string, datei: File): Promise<AusgabeDetail> {
  const fd = new FormData();
  fd.append("datei", datei);
  // Kein Content-Type setzen → Browser schreibt die multipart-boundary.
  return apiClient<AusgabeDetail>(pfad, { method: "PUT", body: fd });
}
export function uploadCover(ausgabeId: number, datei: File): Promise<AusgabeDetail> {
  return uploadAusgabeBild(`${BASE}/${ausgabeId}/cover`, datei);
}
export function deleteCover(ausgabeId: number): Promise<AusgabeDetail> {
  return apiClient<AusgabeDetail>(`${BASE}/${ausgabeId}/cover`, { method: "DELETE" });
}
export function uploadRueck(ausgabeId: number, datei: File): Promise<AusgabeDetail> {
  return uploadAusgabeBild(`${BASE}/${ausgabeId}/rueckseite`, datei);
}
export function deleteRueck(ausgabeId: number): Promise<AusgabeDetail> {
  return apiClient<AusgabeDetail>(`${BASE}/${ausgabeId}/rueckseite`, { method: "DELETE" });
}
