/**
 * Datei-Downloads von admin-gated Endpunkten.
 *
 * apiClient kann hier nicht helfen: der parst JSON. Die Bytes werden daher
 * direkt geholt, mit angehängtem Bearer-Token und einem stillen Refresh-Versuch
 * bei 401 — dasselbe Verhalten, das apiClient sonst übernimmt.
 *
 * Herausgezogen aus maintenanceApi, als das Onboarding-Modul denselben Ablauf
 * brauchte (v1.91).
 */
import { getAccessToken, trySilentRefresh } from "./apiClient";

export async function fetchBlob(url: string): Promise<Blob> {
  const doFetch = () => {
    const token = getAccessToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(url, { headers, credentials: "include" });
  };
  let res = await doFetch();
  if (res.status === 401 && (await trySilentRefresh())) {
    res = await doFetch();
  }
  if (!res.ok) {
    throw new Error(`Download fehlgeschlagen (HTTP ${res.status})`);
  }
  return res.blob();
}

/** Öffnet den Blob in einem neuen Tab (ohne Dateinamen) oder lädt ihn herunter. */
export function openBlob(blob: Blob, filename?: string): void {
  const url = URL.createObjectURL(blob);
  if (filename) {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } else {
    window.open(url, "_blank", "noopener");
  }
  // Erst im nächsten Tick freigeben, damit Navigation bzw. Download die URL
  // noch aufgreifen konnten.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
