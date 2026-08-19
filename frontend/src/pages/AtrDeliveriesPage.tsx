// frontend/src/pages/AtrDeliveriesPage.tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { toast } from "sonner";
import {
  fetchDeliveries, uploadLieferschein, fetchInputFiles, processInputFile,
  deleteDelivery, type AtrDeliverySummary,
} from "@/lib/atrApi";
import { DataTable, type DataTableColumn } from "@/components/DataTable";

type DeliveryRow = AtrDeliverySummary & Record<string, unknown>;

export function AtrDeliveriesPage() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const qc = useQueryClient();
  const [, setLocation] = useLocation();
  const { data: deliveries } = useQuery({ queryKey: ["atr", "deliveries"], queryFn: fetchDeliveries });
  const { data: input } = useQuery({ queryKey: ["atr", "input-files"], queryFn: fetchInputFiles });
  const [busy, setBusy] = useState(false);
  const [picked, setPicked] = useState("");
  const [search, setSearch] = useState("");

  async function onUpload(file: File) {
    setBusy(true);
    try {
      const d = await uploadLieferschein(file);
      qc.invalidateQueries({ queryKey: ["atr", "deliveries"] });
      setLocation(`/atr/deliveries/${d.id}`);
    } catch (e) { toast.error(String(e)); } finally { setBusy(false); }
  }
  async function onProcess() {
    if (!picked) return;
    setBusy(true);
    try {
      const d = await processInputFile(picked);
      qc.invalidateQueries({ queryKey: ["atr", "deliveries"] });
      setLocation(`/atr/deliveries/${d.id}`);
    } catch (e) { toast.error(String(e)); } finally { setBusy(false); }
  }
  async function onDelete(d: DeliveryRow) {
    // Double confirmation before deleting a row.
    if (!window.confirm(t("atr.deliveries.delete_confirm1", { name: d.source_filename }))) return;
    if (!window.confirm(t("atr.deliveries.delete_confirm2"))) return;
    try {
      await deleteDelivery(d.id);
      toast.success(t("atr.deliveries.delete_ok"));
      qc.invalidateQueries({ queryKey: ["atr", "deliveries"] });
    } catch (e) { toast.error(String(e)); }
  }

  const q = search.trim().toLowerCase();
  const rows = (deliveries ?? []).filter(
    (d) => !q
      || d.source_filename.toLowerCase().includes(q)
      || (d.ba_auftrag ?? "").toLowerCase().includes(q)
      || d.status.toLowerCase().includes(q),
  ) as DeliveryRow[];

  const columns: DataTableColumn<DeliveryRow>[] = [
    { key: "source_filename", header: t("atr.deliveries.col.source"), className: "font-medium" },
    { key: "ba_auftrag", header: t("atr.deliveries.col.ba") },
    { key: "atr_number", header: t("atr.deliveries.col.atr_number") },
    { key: "msn", header: t("atr.deliveries.col.msn") },
    { key: "status", header: t("atr.deliveries.col.status") },
    {
      key: "created_at", header: t("atr.deliveries.col.created"), className: "text-muted-foreground",
      cell: (d) => new Date(d.created_at).toLocaleString(locale),
    },
    {
      key: "open", header: "", align: "right", sortable: false,
      cell: (d) => (
        <button className="text-blue-600" onClick={() => setLocation(`/atr/deliveries/${d.id}`)}>
          {t("atr.deliveries.open")}
        </button>
      ),
    },
    {
      key: "delete", header: "", align: "right", sortable: false,
      cell: (d) => (
        <button className="text-red-600" onClick={() => onDelete(d)}
          aria-label={t("atr.deliveries.delete")}>
          {t("atr.deliveries.delete")}
        </button>
      ),
    },
  ];

  const actions = (
    <div className="flex items-center gap-2 flex-wrap">
      <label className="px-3 py-2 border rounded cursor-pointer text-sm">
        {t("atr.deliveries.upload")}
        <input type="file" accept=".pdf" className="hidden" disabled={busy}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); }} />
      </label>
      {input?.configured && (
        <>
          <select className="border rounded px-2 py-2 text-sm" value={picked}
            onChange={(e) => setPicked(e.target.value)} aria-label={t("atr.deliveries.from_folder")}>
            <option value="">{t("atr.deliveries.from_folder")}</option>
            {input.files.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
          <button className="px-3 py-2 border rounded text-sm" disabled={!picked || busy}
            onClick={onProcess}>{t("atr.deliveries.process")}</button>
        </>
      )}
    </div>
  );

  return (
    <DataTable
      actions={actions}
      search={{ value: search, onChange: setSearch, placeholder: t("atr.deliveries.col.source") }}
      columns={columns}
      rows={rows}
      rowKey={(d) => d.id}
      rowTestId={(d) => `atr-delivery-${d.id}`}
      initialSort={{ key: "created_at", dir: "desc" }}
      pageSize={25}
    />
  );
}
