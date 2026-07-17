/**
 * Maschinen-Wartung API adapter — talks to the admin-gated FastAPI router at
 * /api/maintenance. JSON endpoints go through the shared `apiClient` (Bearer
 * token + 401 silent-refresh). Binary endpoints (file proxy, generated PDF) are
 * fetched as raw Blobs with the token attached manually, since apiClient only
 * returns parsed JSON.
 */
import { apiClient, getAccessToken, trySilentRefresh } from "@/lib/apiClient";

export type IntervalType =
  | "daily"
  | "weekly"
  | "monthly"
  | "quarterly"
  | "interval_weeks";
export type MachineStatus = "active" | "inactive";
export type FileKind = "plan" | "archive";

export interface Machine {
  id: string;
  name: string;
  inventory_no: string | null;
  location: string | null;
  manufacturer: string | null;
  model: string | null;
  responsible: string | null;
  status: MachineStatus;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceTask {
  id: string;
  title: string;
  instructions: string;
  interval_type: IntervalType;
  interval_weeks: number | null;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceFile {
  id: string;
  filename: string;
  mime_type: string | null;
  file_kind: FileKind;
  uploaded_at: string;
}

export interface MachineDetail extends Machine {
  tasks: MaintenanceTask[];
  files: MaintenanceFile[];
}

export interface MachineInput {
  name: string;
  inventory_no?: string | null;
  location?: string | null;
  manufacturer?: string | null;
  model?: string | null;
  responsible?: string | null;
  status?: MachineStatus;
  notes?: string;
}

export interface TaskInput {
  title: string;
  instructions?: string;
  interval_type: IntervalType;
  interval_weeks?: number | null;
}

export const maintenanceApi = {
  listMachines: () => apiClient<Machine[]>("/api/maintenance/machines"),

  getMachine: (id: string) =>
    apiClient<MachineDetail>(`/api/maintenance/machines/${id}`),

  createMachine: (body: MachineInput) =>
    apiClient<Machine>("/api/maintenance/machines", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  patchMachine: (id: string, patch: Partial<MachineInput>) =>
    apiClient<Machine>(`/api/maintenance/machines/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  deleteMachine: (id: string) =>
    apiClient<void>(`/api/maintenance/machines/${id}`, { method: "DELETE" }),

  createTask: (machineId: string, body: TaskInput) =>
    apiClient<MaintenanceTask>(
      `/api/maintenance/machines/${machineId}/tasks`,
      { method: "POST", body: JSON.stringify(body) },
    ),

  patchTask: (taskId: string, patch: Partial<TaskInput>) =>
    apiClient<MaintenanceTask>(`/api/maintenance/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  deleteTask: (taskId: string) =>
    apiClient<void>(`/api/maintenance/tasks/${taskId}`, { method: "DELETE" }),

  uploadFile: (machineId: string, file: File, kind: FileKind) => {
    const form = new FormData();
    form.append("file", file);
    form.append("file_kind", kind);
    return apiClient<MachineDetail>(
      `/api/maintenance/machines/${machineId}/files`,
      { method: "POST", body: form },
    );
  },

  deleteFile: (fileId: string) =>
    apiClient<void>(`/api/maintenance/files/${fileId}`, { method: "DELETE" }),
};

/** Fetch bytes from an admin-gated GET endpoint as a Blob (attaches the Bearer
 *  token manually; retries once after a silent refresh on 401). */
async function fetchBlob(url: string): Promise<Blob> {
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

/** Open a blob in a new tab (file preview) or trigger a download. */
function openBlob(blob: Blob, filename?: string): void {
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
  // Revoke on the next tick so the navigation/download has picked up the URL.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export async function downloadMachineSheet(
  machineId: string,
  machineName: string,
  opts?: { year?: number; half?: 1 | 2 },
): Promise<void> {
  const q = new URLSearchParams();
  if (opts?.year) q.set("year", String(opts.year));
  if (opts?.half) q.set("half", String(opts.half));
  const qs = q.toString();
  const blob = await fetchBlob(
    `/api/maintenance/machines/${machineId}/sheet.pdf${qs ? `?${qs}` : ""}`,
  );
  openBlob(blob, `Wartungsnachweis_${machineName}.pdf`);
}

export async function openMaintenanceFile(fileId: string): Promise<void> {
  const blob = await fetchBlob(`/api/maintenance/files/${fileId}`);
  openBlob(blob);
}
