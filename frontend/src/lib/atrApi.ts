// frontend/src/lib/atrApi.ts
import { apiClient } from "./apiClient";

/**
 * Pad a purely numeric PO position to 3 digits with leading zeros
 * ("5" -> "005", "50" -> "050"). Empty, non-numeric, or already
 * longer-than-3-digit values are returned unchanged. Mirrors the
 * backend `normalize_po_pos`.
 */
export function formatPoPos(value: string | null | undefined): string {
  if (value == null) return "";
  const s = value.trim();
  if (/^\d{1,3}$/.test(s)) return s.padStart(3, "0");
  return value;
}

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
  po_pos?: string | null; // editable from AtrPartsPage
}

export interface AtrPartCreate {
  part_number: string;
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

export async function createAtrPart(body: AtrPartCreate): Promise<AtrPart> {
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

export interface AtrDeliveryItem {
  id: number; pos: number | null; supplier_article_code: string | null;
  part_number: string | null; part_number_norm: string | null;
  matched_part_id: number | null; part_name: string | null;
  drawing_number_issue: string | null; category: string | null; qty: number;
  weight_kg: string | null; po_pos: string | null; match_status: string; row_order: number;
}
export interface AtrDelivery {
  id: number; source_filename: string; lieferschein_nr: string | null; datum: string | null;
  ba_auftrag: string | null; po_number: string | null; ac_programme: string | null;
  compartment: string | null; msn: string | null; bed_config: string | null;
  set_title: string | null; atr_number: string | null; container_number: string | null;
  weighing_date: string | null; testing_date: string | null; qa_signer: string | null;
  max_guaranteed_weight_kg: string | null; status: string;
  created_at: string; updated_at: string; items: AtrDeliveryItem[];
}
export interface AtrDeliverySummary {
  id: number; source_filename: string; ba_auftrag: string | null;
  compartment: string | null; status: string; created_at: string;
}
export interface AtrGenerateManifest {
  delivery_id: number; files: string[]; pdf_available: boolean;
  unmatched_count: number; warnings: string[];
}
export interface AtrInputFiles { configured: boolean; files: string[]; }

export async function uploadLieferschein(file: File): Promise<AtrDelivery> {
  const fd = new FormData(); fd.append("file", file);
  return apiClient<AtrDelivery>("/api/atr/deliveries/upload", { method: "POST", body: fd });
}
export async function fetchInputFiles(): Promise<AtrInputFiles> {
  return apiClient<AtrInputFiles>("/api/atr/deliveries/input-files");
}
export async function processInputFile(filename: string): Promise<AtrDelivery> {
  return apiClient<AtrDelivery>("/api/atr/deliveries/input-files/process", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  });
}
export async function fetchDeliveries(): Promise<AtrDeliverySummary[]> {
  return apiClient<AtrDeliverySummary[]>("/api/atr/deliveries");
}
export async function fetchDelivery(id: number): Promise<AtrDelivery> {
  return apiClient<AtrDelivery>(`/api/atr/deliveries/${id}`);
}
export async function updateDelivery(id: number, body: Partial<AtrDelivery>): Promise<AtrDelivery> {
  return apiClient<AtrDelivery>(`/api/atr/deliveries/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
}
export async function updateDeliveryItem(
  did: number, iid: number, body: Partial<AtrDeliveryItem>,
): Promise<AtrDeliveryItem> {
  return apiClient<AtrDeliveryItem>(`/api/atr/deliveries/${did}/items/${iid}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
}
export async function generateDelivery(id: number): Promise<AtrGenerateManifest> {
  return apiClient<AtrGenerateManifest>(`/api/atr/deliveries/${id}/generate`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
  });
}
export function atrFileUrl(id: number, kind: "atr_xlsx" | "atr_pdf" | "label_docx"): string {
  return `/api/atr/deliveries/${id}/files/${kind}`;
}
