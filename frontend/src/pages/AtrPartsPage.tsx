import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { Pencil, Check, Trash2, Plus } from "lucide-react";
import { toast } from "sonner";
import {
  fetchAtrParts, updateAtrPart, deleteAtrPart, createAtrPart,
  type AtrPart, type AtrPartCreate,
} from "@/lib/atrApi";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { AtrDeliveriesPage } from "@/pages/AtrDeliveriesPage";

type PartRow = AtrPart & Record<string, unknown>;
const EMPTY_NEW: AtrPartCreate = { part_number: "" };

export function AtrPartsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  // View is URL-driven so the SubHeader dropdown can switch it: /atr shows the
  // deliveries list (default), /atr/teilekatalog shows the parts catalog.
  const [location] = useLocation();
  const tab: "parts" | "deliveries" = location === "/atr/teilekatalog" ? "parts" : "deliveries";
  const [search, setSearch] = useState("");
  const { data: parts, isLoading } = useQuery({
    queryKey: ["atr", "parts", search],
    queryFn: () => fetchAtrParts(search || undefined),
    enabled: tab === "parts",
  });
  const [editId, setEditId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Partial<AtrPart>>({});
  const [showAdd, setShowAdd] = useState(false);
  const [newPart, setNewPart] = useState<AtrPartCreate>(EMPTY_NEW);

  const create = useMutation({
    mutationFn: () => createAtrPart({
      ...newPart,
      part_number: newPart.part_number.trim(),
    }),
    onSuccess: () => {
      toast.success(t("atr.parts.created"));
      setNewPart(EMPTY_NEW);
      setShowAdd(false);
      qc.invalidateQueries({ queryKey: ["atr", "parts"] });
    },
    onError: (e: unknown) => toast.error(String(e)),
  });

  const save = useMutation({
    mutationFn: (id: number) => updateAtrPart(id, {
      default_weight_kg: draft.default_weight_kg ?? null,
      drawing_number_issue: draft.drawing_number_issue ?? null,
      part_name: draft.part_name ?? null,
    }),
    onSuccess: () => {
      toast.success(t("atr.parts.save"));
      setEditId(null);
      qc.invalidateQueries({ queryKey: ["atr", "parts"] });
    },
    onError: (e: unknown) => toast.error(String(e)),
  });
  const remove = useMutation({
    mutationFn: (id: number) => deleteAtrPart(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["atr", "parts"] }),
  });

  const columns: DataTableColumn<PartRow>[] = [
    { key: "part_number", header: t("atr.parts.col.part_number"), className: "font-mono" },
    {
      key: "part_name", header: t("atr.parts.col.name"),
      cell: (p) => editId === p.id ? (
        <input className="border rounded px-1" defaultValue={p.part_name ?? ""}
          onChange={(e) => setDraft((d) => ({ ...d, part_name: e.target.value }))} />
      ) : p.part_name ?? "—",
    },
    { key: "category", header: t("atr.parts.col.category") },
    {
      key: "drawing_number_issue", header: t("atr.parts.col.drawing"),
      cell: (p) => editId === p.id ? (
        <input className="border rounded px-1" defaultValue={p.drawing_number_issue ?? ""}
          onChange={(e) => setDraft((d) => ({ ...d, drawing_number_issue: e.target.value }))} />
      ) : p.drawing_number_issue ?? "—",
    },
    {
      key: "default_weight_kg", header: t("atr.parts.col.weight"),
      cell: (p) => editId === p.id ? (
        <input className="border rounded px-1 w-20" defaultValue={p.default_weight_kg ?? ""}
          onChange={(e) => setDraft((d) => ({ ...d, default_weight_kg: e.target.value }))} />
      ) : p.default_weight_kg ?? "—",
    },
    { key: "source_filename", header: t("atr.parts.col.source"), className: "text-xs text-muted-foreground" },
    {
      key: "actions", header: "", align: "right", sortable: false, className: "whitespace-nowrap",
      cell: (p) => (
        <span className="inline-flex items-center gap-3">
          {editId === p.id ? (
            <button className="text-blue-600" aria-label={t("atr.parts.save")} title={t("atr.parts.save")}
              onClick={() => save.mutate(p.id)}>
              <Check className="h-4 w-4" />
            </button>
          ) : (
            <button className="text-blue-600" aria-label={t("atr.parts.edit")} title={t("atr.parts.edit")}
              onClick={() => { setEditId(p.id); setDraft(p); }}>
              <Pencil className="h-4 w-4" />
            </button>
          )}
          <button className="text-red-600" aria-label={t("atr.parts.delete")} title={t("atr.parts.delete")}
            onClick={() => remove.mutate(p.id)}>
            <Trash2 className="h-4 w-4" />
          </button>
        </span>
      ),
    },
  ];

  const nfield = (key: keyof AtrPartCreate, label: string, required = false) => (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-muted-foreground">{label}{required ? " *" : ""}</span>
      <input className="border rounded px-2 py-1.5"
        value={(newPart[key] as string | undefined) ?? ""}
        onChange={(e) => setNewPart((p) => ({ ...p, [key]: e.target.value }))} />
    </label>
  );

  return (
    <div className="max-w-6xl mx-auto px-6 py-6">
      {tab === "parts" ? (
        <div className="space-y-4">
          {showAdd && (
            <div className="border rounded-lg p-4 bg-card">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {nfield("part_number", t("atr.parts.col.part_number"), true)}
                {nfield("part_name", t("atr.parts.col.name"))}
                {nfield("category", t("atr.parts.col.category"))}
                {nfield("drawing_number_issue", t("atr.parts.col.drawing"))}
                {nfield("default_weight_kg", t("atr.parts.col.weight"))}
                {nfield("po_pos", t("atr.parts.col.po_pos"))}
                {nfield("supplier_article_code", t("atr.parts.col.supplier_code"))}
              </div>
              <div className="mt-4 flex gap-2">
                <button
                  className="rounded-md bg-primary text-primary-foreground px-3 py-1.5 text-sm hover:opacity-90 disabled:opacity-50"
                  disabled={!newPart.part_number.trim() || create.isPending}
                  onClick={() => create.mutate()}
                >
                  {t("atr.parts.create")}
                </button>
                <button
                  className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent/10"
                  onClick={() => { setShowAdd(false); setNewPart(EMPTY_NEW); }}
                >
                  {t("common.cancel")}
                </button>
              </div>
            </div>
          )}
          <DataTable
            actions={
              <button
                className="inline-flex items-center gap-1.5 rounded-md bg-primary text-primary-foreground px-3 py-1.5 text-sm hover:opacity-90"
                onClick={() => setShowAdd((v) => !v)}
              >
                <Plus className="h-4 w-4" />
                {t("atr.parts.add")}
              </button>
            }
            search={{ value: search, onChange: setSearch, placeholder: t("atr.parts.search") }}
            columns={columns}
            rows={(parts ?? []) as PartRow[]}
            rowKey={(p) => p.id}
            rowTestId={(p) => `atr-part-${p.id}`}
            isLoading={isLoading}
            emptyText={t("atr.parts.empty")}
            initialSort={{ key: "part_number", dir: "asc" }}
            pageSize={25}
            minWidth={880}
          />
        </div>
      ) : (
        <AtrDeliveriesPage />
      )}
    </div>
  );
}
