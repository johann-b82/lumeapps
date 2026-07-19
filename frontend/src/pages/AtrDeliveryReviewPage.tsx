// frontend/src/pages/AtrDeliveryReviewPage.tsx
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRoute } from "wouter";
import { toast } from "sonner";
import {
  fetchDelivery, updateDelivery, updateDeliveryItem, generateDelivery,
  atrFileUrl, type AtrDelivery, type AtrDeliveryItem,
} from "@/lib/atrApi";
import { DataTable, type DataTableColumn } from "@/components/DataTable";

type ItemRow = AtrDeliveryItem & Record<string, unknown>;

const HEADER_FIELDS: (keyof AtrDelivery)[] = [
  "atr_number", "container_number", "set_title", "po_number",
  "weighing_date", "testing_date", "qa_signer", "max_guaranteed_weight_kg",
];

export function AtrDeliveryReviewPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [, params] = useRoute("/atr/deliveries/:id");
  const id = Number(params?.id);
  const { data } = useQuery({ queryKey: ["atr", "delivery", id], queryFn: () => fetchDelivery(id), enabled: !!id });
  const [draft, setDraft] = useState<Partial<AtrDelivery>>({});
  const [manifest, setManifest] = useState<string[] | null>(null);
  useEffect(() => { if (data) setDraft(data); }, [data]);

  async function saveHeader() {
    try {
      const body: Record<string, unknown> = {};
      HEADER_FIELDS.forEach((f) => { body[f] = (draft as Record<string, unknown>)[f] ?? null; });
      await updateDelivery(id, body as Partial<AtrDelivery>);
      toast.success(t("atr.deliveries.save"));
      qc.invalidateQueries({ queryKey: ["atr", "delivery", id] });
    } catch (e) { toast.error(String(e)); }
  }
  async function saveItem(iid: number, weight: string, po: string) {
    try {
      await updateDeliveryItem(id, iid, { weight_kg: weight || null, po_pos: po || null });
      qc.invalidateQueries({ queryKey: ["atr", "delivery", id] });
    } catch (e) { toast.error(String(e)); }
  }
  async function onGenerate() {
    try {
      const m = await generateDelivery(id);
      setManifest(m.files);
      m.warnings.forEach((w) => toast.warning(w));
      if (!m.warnings.length) toast.success(t("atr.deliveries.generate"));
    } catch (e) { toast.error(String(e)); }
  }

  const itemColumns: DataTableColumn<ItemRow>[] = [
    { key: "part_number", header: t("atr.deliveries.item.part_number"), className: "font-mono" },
    { key: "part_name", header: t("atr.deliveries.item.name") },
    { key: "drawing_number_issue", header: t("atr.deliveries.item.drawing") },
    {
      key: "weight_kg", header: t("atr.deliveries.item.weight"),
      cell: (it) => (
        <input className="border rounded px-1 w-20" defaultValue={it.weight_kg ?? ""}
          onBlur={(e) => saveItem(it.id, e.target.value, it.po_pos ?? "")} />
      ),
    },
    {
      key: "po_pos", header: t("atr.deliveries.item.po_pos"),
      cell: (it) => (
        <input className="border rounded px-1 w-16" defaultValue={it.po_pos ?? ""}
          onBlur={(e) => saveItem(it.id, it.weight_kg ?? "", e.target.value)} />
      ),
    },
  ];

  if (!data) return <div className="p-6">…</div>;
  return (
    <div className="max-w-5xl mx-auto px-6 py-6">
      <h1 className="text-xl font-semibold mb-4">
        {t("atr.deliveries.review.heading")} — {data.source_filename}
      </h1>
      <div className="grid grid-cols-2 gap-3 mb-6">
        {HEADER_FIELDS.map((f) => (
          <label key={f} className="flex flex-col text-sm">
            <span className="text-muted-foreground">{t(`atr.deliveries.field.${f === "max_guaranteed_weight_kg" ? "max_weight" : f}`)}</span>
            <input className="border rounded px-2 py-1"
              value={(draft[f] as string) ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, [f]: e.target.value }))} />
          </label>
        ))}
      </div>
      <button className="mb-4 px-3 py-1 border rounded" onClick={saveHeader}>{t("atr.deliveries.save")}</button>

      <div className="mb-6">
        <DataTable
          card={false}
          columns={itemColumns}
          rows={data.items as ItemRow[]}
          rowKey={(it) => it.id}
          rowTestId={(it) => `atr-item-${it.id}`}
          rowClassName={(it) => it.match_status !== "matched" ? "bg-red-100" : ""}
        />
      </div>

      <button className="px-4 py-2 bg-blue-600 text-white rounded mr-4" onClick={onGenerate}>
        {t("atr.deliveries.generate")}
      </button>
      {manifest && (
        <span className="inline-flex gap-3">
          {manifest.includes("atr_xlsx") && <a className="text-blue-600" href={atrFileUrl(id, "atr_xlsx")}>{t("atr.deliveries.download_xlsx")}</a>}
          {manifest.includes("atr_pdf") && <a className="text-blue-600" href={atrFileUrl(id, "atr_pdf")}>{t("atr.deliveries.download_pdf")}</a>}
          {manifest.includes("label_docx") && <a className="text-blue-600" href={atrFileUrl(id, "label_docx")}>{t("atr.deliveries.download_docx")}</a>}
        </span>
      )}
    </div>
  );
}
