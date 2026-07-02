/**
 * FAIR (Erstmusterprüfung) API adapter — talks to the admin-gated FastAPI
 * router at /api/fair. JSON endpoints go through the shared `apiClient` (Bearer
 * token + 401 silent-refresh). The drawing file proxy is fetched as a raw Blob
 * with the token attached manually (apiClient only returns parsed JSON), so the
 * bytes can back both an <img> and react-pdf via an object URL.
 */
import { apiClient, getAccessToken, trySilentRefresh } from "@/lib/apiClient";

export type FairFileKind = "pdf" | "image";

export interface FairProject {
  id: string;
  name: string;
  part_number: string | null;
  customer: string | null;
  article_number: string | null;
  file_kind: FairFileKind;
  mime_type: string | null;
  page_count: number;
  rotation: number;
  created_at: string;
  updated_at: string;
}

export interface FairBalloon {
  id: string;
  number: number;
  page_no: number;
  region_x: number;
  region_y: number;
  region_w: number;
  region_h: number;
  tail_x: number;
  tail_y: number;
  value_text: string;
}

export interface FairProjectDetail extends FairProject {
  balloons: FairBalloon[];
}

export interface BalloonInput {
  page_no: number;
  region_x: number;
  region_y: number;
  region_w: number;
  region_h: number;
  tail_x: number;
  tail_y: number;
  value_text: string;
}

export type BalloonPatch = Partial<BalloonInput>;

export const fairApi = {
  listProjects: () => apiClient<FairProject[]>("/api/fair/projects"),

  getProject: (id: string) =>
    apiClient<FairProjectDetail>(`/api/fair/projects/${id}`),

  createProject: (file: File, name?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (name) form.append("name", name);
    return apiClient<FairProject>("/api/fair/projects", {
      method: "POST",
      body: form,
    });
  },

  patchProject: (
    id: string,
    patch: {
      name?: string;
      part_number?: string | null;
      customer?: string | null;
      article_number?: string | null;
      page_count?: number;
      rotation?: number;
    },
  ) =>
    apiClient<FairProject>(`/api/fair/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  deleteProject: (id: string) =>
    apiClient<void>(`/api/fair/projects/${id}`, { method: "DELETE" }),

  createBalloon: (projectId: string, input: BalloonInput) =>
    apiClient<FairBalloon>(`/api/fair/projects/${projectId}/balloons`, {
      method: "POST",
      body: JSON.stringify(input),
    }),

  reorderBalloons: (projectId: string, orderedIds: string[]) =>
    apiClient<FairBalloon[]>(
      `/api/fair/projects/${projectId}/balloons/reorder`,
      { method: "POST", body: JSON.stringify({ ordered_ids: orderedIds }) },
    ),

  getBalloon: (balloonId: string) =>
    apiClient<FairBalloon>(`/api/fair/balloons/${balloonId}`),

  patchBalloon: (balloonId: string, patch: BalloonPatch) =>
    apiClient<FairBalloon>(`/api/fair/balloons/${balloonId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  deleteBalloon: (balloonId: string) =>
    apiClient<void>(`/api/fair/balloons/${balloonId}`, { method: "DELETE" }),
};

/**
 * Fetch the stored drawing bytes through the backend proxy. Attaches the Bearer
 * token manually (a bare fetch would not) and also sends the session cookie via
 * `credentials: include`; retries once after a silent token refresh on 401.
 */
export async function fetchDrawingBlob(projectId: string): Promise<Blob> {
  const url = `/api/fair/projects/${projectId}/file`;
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
    throw new Error(`Zeichnung konnte nicht geladen werden (HTTP ${res.status})`);
  }
  return res.blob();
}
