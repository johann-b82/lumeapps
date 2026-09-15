/**
 * Produktions-Priorisierung API adapter — admin-gated FastAPI router at
 * /api/production/prio. JSON via `apiClient`, Excel-Export als Blob.
 */
import { apiClient } from "@/lib/apiClient";
import { fetchBlob, openBlob } from "@/lib/download";

export type ImportQuelle = "artikelstamm" | "ressourcenplan" | "auftraege";

export interface ImportStand {
  quelle: ImportQuelle;
  dateiname: string | null;
  zeilen: number;
  warnungen: number;
  importiert_am: string;
}

export interface PrioListe {
  id: number;
  name: string;
  typ: string;
  stand: string;
  dateiname: string | null;
  importiert_am: string;
  eintraege: number;
  mit_rang: number;
}

export interface PrioStatus {
  importe: ImportStand[];
  listen: PrioListe[];
}

export interface ImportErgebnis {
  zeilen: number;
  warnungen: string[];
  warnungen_anzahl: number;
}

export interface PositionZeile {
  pos: number;
  upos: number;
  artikelnr: string | null;
  bezeichnung: string | null;
  menge: string | null;
  einheit: string | null;
  lieferdatum: string | null;
  termin: string | null;
  liste: string | null;
  listen_rang: number | null;
  kommentar: string | null;
  gesperrt: boolean;
  ohne_plan: boolean;
}

/** Ein BA der Gesamtliste; seine Positionen (FAs) laufen mit. */
export interface BaZeile {
  rang: number;
  vorgang_nr: string;
  kunde: string | null;
  termin: string | null;
  listen_rang: number | null;
  gesperrt: boolean;
  manuell: boolean;
  positionen: PositionZeile[];
}

export interface Bereich {
  key: string;
  label: string;
  taetigkeiten: number;
  minuten: string;
}

export interface BereichsZeile {
  prio: number;
  vorgang_nr: string;
  pos: number;
  upos: number;
  termin: string | null;
  kunde: string | null;
  endartikel: string | null;
  endartikel_bez: string | null;
  ebene: number;
  pfad: string;
  artikelnr: string;
  artikel_bez: string | null;
  ressource: string;
  kostenstelle: string | null;
  taetigkeit: string | null;
  menge: string;
  minuten: string;
  gesperrt: boolean;
  kommentar: string | null;
}

const BASE = "/api/production/prio";

function upload(path: string, file: File): Promise<ImportErgebnis> {
  const form = new FormData();
  form.append("file", file);
  return apiClient<ImportErgebnis>(`${BASE}${path}`, { method: "POST", body: form });
}

export const prioApi = {
  status: () => apiClient<PrioStatus>(`${BASE}/status`),
  importQuelle: (quelle: ImportQuelle, file: File) => upload(`/import/${quelle}`, file),
  importListe: (file: File) => upload("/import/liste", file),
  deleteListe: (id: number) => apiClient<void>(`${BASE}/listen/${id}`, { method: "DELETE" }),
  gesamt: () => apiClient<BaZeile[]>(`${BASE}/gesamt`),
  /** BA-Nummern in der gewünschten Reihenfolge. */
  saveManuell: (reihenfolge: string[]) =>
    apiClient<void>(`${BASE}/manuell`, { method: "PUT", body: JSON.stringify({ reihenfolge }) }),
  resetManuell: () => apiClient<void>(`${BASE}/manuell`, { method: "DELETE" }),
  bereiche: () => apiClient<Bereich[]>(`${BASE}/bereiche`),
  bereich: (key: string) => apiClient<BereichsZeile[]>(`${BASE}/bereiche/${key}`),
};

export async function exportBereich(key: string): Promise<void> {
  const blob = await fetchBlob(`${BASE}/bereiche/${key}/export.xlsx`);
  openBlob(blob, `Prioliste_${key}.xlsx`);
}
