/**
 * Befund 9: jede Anfrage der Oberfläche trägt X-LumeApps-Request.
 *
 * Ohne diese Kopfzeile weist das Backend jede verändernde Anfrage ab, die
 * sich über das Sitzungs-Cookie ausweist — dann wäre die Oberfläche kaputt.
 * Der Test hält beide Richtungen fest: die Kopfzeile ist da, und ein
 * FormData-Rumpf bekommt weiterhin kein erzwungenes Content-Type.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient, setAccessToken } from "./apiClient";

function fangeAnfrage() {
  const gesehen: { url: string; init: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit) => {
      gesehen.push({ url, init });
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return gesehen;
}

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessToken(null);
});

describe("apiClient", () => {
  it("hängt X-LumeApps-Request an jede Anfrage", async () => {
    const gesehen = fangeAnfrage();
    await apiClient("/api/kpis");
    const kopf = gesehen[0].init.headers as Record<string, string>;
    expect(kopf["X-LumeApps-Request"]).toBe("1");
  });

  it("hängt sie auch an verändernde Anfragen", async () => {
    const gesehen = fangeAnfrage();
    await apiClient("/api/settings", { method: "PUT", body: "{}" });
    const kopf = gesehen[0].init.headers as Record<string, string>;
    expect(kopf["X-LumeApps-Request"]).toBe("1");
    expect(kopf["Content-Type"]).toBe("application/json");
  });

  it("erzwingt bei FormData weiterhin kein Content-Type", async () => {
    const gesehen = fangeAnfrage();
    const daten = new FormData();
    daten.append("file", new Blob(["x"]), "a.csv");
    await apiClient("/api/upload", { method: "POST", body: daten });
    const kopf = gesehen[0].init.headers as Record<string, string>;
    expect(kopf["X-LumeApps-Request"]).toBe("1");
    expect(kopf["Content-Type"]).toBeUndefined();
  });
});
