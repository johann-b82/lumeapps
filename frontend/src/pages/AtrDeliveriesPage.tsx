// frontend/src/pages/AtrDeliveriesPage.tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { toast } from "sonner";
import {
  fetchDeliveries, uploadLieferschein, fetchInputFiles, processInputFile,
  deleteDelivery, updateDelivery, containerLabelUrl, type AtrDeliverySummary,
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
  // Multi-select for the container label (ids survive paging/filtering).
  const [selected, setSelected] = useState<Set<number>>(new Set());

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

  function toggle(id: number, on: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (on) next.add(id); else next.delete(id);
      return next;
    });
  }
  async function onContainerLabel() {
    const picked = (deliveries ?? []).filter((d) => selected.has(d.id));
    if (picked.length === 0) return;
    // Prefill when every selected delivery already sits in the same container.
    const first = picked[0].container_number ?? "";
    const common = first && picked.every((d) => (d.container_number ?? "") === first) ? first : "";
    const nr = window.prompt(t("atr.deliveries.container_prompt"), common)?.trim();
    if (!nr) return;
    setBusy(true);
    try {
      await Promise.all(picked.map((d) => updateDelivery(d.id, { container_number: nr })));
      qc.invalidateQueries({ queryKey: ["atr", "deliveries"] });
      setSelected(new Set());
      toast.success(t("atr.deliveries.container_label_ok", { nr }));
      // Same cookie-authenticated download path as the per-delivery file links.
      const a = document.createElement("a");
      a.href = containerLabelUrl(nr);
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (e) { toast.error(String(e)); } finally { setBusy(false); }
  }

  const q = search.trim().toLowerCase();
  const rows = (deliveries ?? []).filter(
    (d) => !q
      || d.source_filename.toLowerCase().includes(q)
      || (d.ba_auftrag ?? "").toLowerCase().includes(q)
      || (d.container_number ?? "").toLowerCase().includes(q)
      || d.status.toLowerCase().includes(q),
  ) as DeliveryRow[];
  const allSelected = rows.length > 0 && rows.every((d) => selected.has(d.id));

  const columns: DataTableColumn<DeliveryRow>[] = [
    {
      key: "select", sortable: false,
      header: (
        <input type="checkbox" checked={allSelected} aria-label={t("atr.deliveries.select_all")}
          onChange={(e) => setSelected(e.target.checked ? new Set(rows.map((d) => d.id)) : new Set())} />
      ),
      cell: (d) => (
        <input type="checkbox" checked={selected.has(d.id)} aria-label={t("atr.deliveries.select_row")}
          data-testid={`atr-delivery-select-${d.id}`}
          onChange={(e) => toggle(d.id, e.target.checked)} />
      ),
    },
    { key: "source_filename", header: t("atr.deliveries.col.source"), className: "font-medium" },
    { key: "ba_auftrag", header: t("atr.deliveries.col.ba") },
    { key: "atr_number", header: t("atr.deliveries.col.atr_number") },
    { key: "container_number", header: t("atr.deliveries.col.container") },
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
      <button className="px-3 py-2 border rounded text-sm disabled:opacity-50"
        disabled={selected.size === 0 || busy} onClick={onContainerLabel}>
        {t("atr.deliveries.container_label")}{selected.size > 0 ? ` (${selected.size})` : ""}
      </button>
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
