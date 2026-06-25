// frontend/src/lib/atrApi.ts
import { apiClient } from "./apiClient";

export interface AtrPart {
  id: number;
  part_number: string;
  part_number_norm: string;
  supplier_article_code: string | null;
  part_name: string | null;
  drawing_number_issue: string | null;
  default_weight_kg: string | null; // Decimal as string
  qty: number;
  category: string | null;
  po_pos: string | null;
  source_filename: string;
  imported_at: string;
  updated_at: string;
}

export interface AtrPartUpdate {
  part_number?: string;
  supplier_article_code?: string | null;
  part_name?: string | null;
  drawing_number_issue?: string | null;
  default_weight_kg?: string | null;
  qty?: number;
  category?: string | null;
  po_pos?: string | null;
}

export interface AtrTemplate {
  id: number;
  customer: string | null;
  ac_programme: string | null;
  work_package: string | null;
  purchaser_spec: string | null;
  atp: string | null;
  supplier_spec: string | null;
  reference_no: string | null;
  supplier: string | null;
  customer_spec: string | null;
  nscm_code: string | null;
  ata_chapter: string | null;
  weighing_equipment: string | null;
  qa_signer_default: string | null;
  structure_filename: string | null;
  has_structure: boolean;
  updated_at: string;
}

export interface AtrImportPartPreview {
  part_number: string;
  part_number_norm: string;
  supplier_article_code: string | null;
  part_name: string | null;
  drawing_number_issue: string | null;
  default_weight_kg: string | null;
  qty: number;
  category: string | null;
  status: "new" | "updated" | "unchanged";
}

export interface AtrImportPreview {
  source_filename: string;
  header: Record<string, string | null>;
  parts: AtrImportPartPreview[];
  new_count: number;
  updated_count: number;
  unchanged_count: number;
  warnings: string[];
}

export interface AtrImportResult {
  source_filename: string;
  created: number;
  updated: number;
  template_updated: boolean;
  structure_set: boolean;
  warnings: string[];
}

export async function fetchAtrParts(search?: string): Promise<AtrPart[]> {
  const qs = search ? `?search=${encodeURIComponent(search)}` : "";
  return apiClient<AtrPart[]>(`/api/atr/parts${qs}`);
}

export async function createAtrPart(body: { part_number: string }): Promise<AtrPart> {
  return apiClient<AtrPart>("/api/atr/parts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function updateAtrPart(id: number, body: AtrPartUpdate): Promise<AtrPart> {
  return apiClient<AtrPart>(`/api/atr/parts/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function deleteAtrPart(id: number): Promise<void> {
  await apiClient<void>(`/api/atr/parts/${id}`, { method: "DELETE" });
}

export async function fetchAtrTemplate(): Promise<AtrTemplate> {
  return apiClient<AtrTemplate>("/api/atr/template");
}

export async function updateAtrTemplate(body: Partial<AtrTemplate>): Promise<AtrTemplate> {
  return apiClient<AtrTemplate>("/api/atr/template", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function atrImportPreview(files: File[]): Promise<AtrImportPreview[]> {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  return apiClient<AtrImportPreview[]>("/api/atr/import/preview", {
    method: "POST",
    body: fd,
  });
}

export async function atrImportCommit(
  files: File[],
  opts?: { update_template?: boolean; set_structure?: boolean },
): Promise<AtrImportResult[]> {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  fd.append("update_template", String(opts?.update_template ?? false));
  fd.append("set_structure", String(opts?.set_structure ?? false));
  return apiClient<AtrImportResult[]>("/api/atr/import/commit", {
    method: "POST",
    body: fd,
  });
}

export async function setAtrStructure(file: File): Promise<AtrTemplate> {
  const fd = new FormData();
  fd.append("file", file);
  return apiClient<AtrTemplate>("/api/atr/template/structure", {
    method: "POST",
    body: fd,
  });
}
