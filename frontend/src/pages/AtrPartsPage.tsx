import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { toast } from "sonner";
import {
  fetchAtrParts, updateAtrPart, deleteAtrPart, type AtrPart,
} from "@/lib/atrApi";
import { DataTable, type DataTableColumn } from "@/components/DataTable";

type PartRow = AtrPart & Record<string, unknown>;

export function AtrPartsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [, setLocation] = useLocation();
  const [search, setSearch] = useState("");
  const { data: parts, isLoading } = useQuery({
    queryKey: ["atr", "parts", search],
    queryFn: () => fetchAtrParts(search || undefined),
  });
  const [editId, setEditId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Partial<AtrPart>>({});

  const save = useMutation({
    mutationFn: (id: number) => updateAtrPart(id, {
      po_pos: draft.po_pos ?? null,
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
    {
      key: "po_pos", header: t("atr.parts.col.po_pos"),
      cell: (p) => editId === p.id ? (
        <input className="border rounded px-1 w-16" defaultValue={p.po_pos ?? ""}
          onChange={(e) => setDraft((d) => ({ ...d, po_pos: e.target.value }))} />
      ) : p.po_pos ?? "—",
    },
    { key: "source_filename", header: t("atr.parts.col.source"), className: "text-xs text-muted-foreground" },
    {
      key: "actions", header: "", sortable: false, className: "whitespace-nowrap",
      cell: (p) => (
        <>
          {editId === p.id ? (
            <button className="text-blue-600 mr-2" onClick={() => save.mutate(p.id)}>
              {t("atr.parts.save")}
            </button>
          ) : (
            <button className="text-blue-600 mr-2"
              onClick={() => { setEditId(p.id); setDraft(p); }}>
              {t("atr.parts.edit")}
            </button>
          )}
          <button className="text-red-600" onClick={() => remove.mutate(p.id)}>
            {t("atr.parts.delete")}
          </button>
        </>
      ),
    },
  ];

  return (
    <div className="max-w-6xl mx-auto px-6 py-6">
      <DataTable
        title={t("atr.parts.heading")}
        actions={
          <button className="px-3 py-2 border rounded text-sm"
            onClick={() => setLocation("/atr/deliveries")}>
            {t("atr.nav.deliveries")} →
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
  );
}
