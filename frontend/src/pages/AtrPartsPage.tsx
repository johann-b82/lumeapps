import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  fetchAtrParts, updateAtrPart, deleteAtrPart, type AtrPart,
} from "@/lib/atrApi";

export function AtrPartsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
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

  return (
    <div className="max-w-6xl mx-auto px-6 py-6">
      <h1 className="text-xl font-semibold mb-4">{t("atr.parts.heading")}</h1>
      <input
        className="border rounded px-3 py-2 mb-4 w-full max-w-md"
        placeholder={t("atr.parts.search")}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        aria-label={t("atr.parts.search")}
      />
      {isLoading ? (
        <p>…</p>
      ) : !parts || parts.length === 0 ? (
        <p className="text-muted-foreground">{t("atr.parts.empty")}</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left border-b">
              <th className="py-2">{t("atr.parts.col.part_number")}</th>
              <th>{t("atr.parts.col.name")}</th>
              <th>{t("atr.parts.col.category")}</th>
              <th>{t("atr.parts.col.drawing")}</th>
              <th>{t("atr.parts.col.weight")}</th>
              <th>{t("atr.parts.col.po_pos")}</th>
              <th>{t("atr.parts.col.source")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {parts.map((p) => {
              const editing = editId === p.id;
              return (
                <tr key={p.id} className="border-b" data-testid={`atr-part-${p.id}`}>
                  <td className="py-1 font-mono">{p.part_number}</td>
                  <td>{editing ? (
                    <input className="border rounded px-1" defaultValue={p.part_name ?? ""}
                      onChange={(e) => setDraft((d) => ({ ...d, part_name: e.target.value }))} />
                  ) : p.part_name}</td>
                  <td>{p.category}</td>
                  <td>{editing ? (
                    <input className="border rounded px-1" defaultValue={p.drawing_number_issue ?? ""}
                      onChange={(e) => setDraft((d) => ({ ...d, drawing_number_issue: e.target.value }))} />
                  ) : p.drawing_number_issue}</td>
                  <td>{editing ? (
                    <input className="border rounded px-1 w-20" defaultValue={p.default_weight_kg ?? ""}
                      onChange={(e) => setDraft((d) => ({ ...d, default_weight_kg: e.target.value }))} />
                  ) : p.default_weight_kg}</td>
                  <td>{editing ? (
                    <input className="border rounded px-1 w-16" defaultValue={p.po_pos ?? ""}
                      onChange={(e) => setDraft((d) => ({ ...d, po_pos: e.target.value }))} />
                  ) : p.po_pos}</td>
                  <td className="text-xs text-muted-foreground">{p.source_filename}</td>
                  <td className="whitespace-nowrap">
                    {editing ? (
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
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
