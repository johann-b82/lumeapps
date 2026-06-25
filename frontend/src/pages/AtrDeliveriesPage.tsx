// frontend/src/pages/AtrDeliveriesPage.tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { toast } from "sonner";
import {
  fetchDeliveries, uploadLieferschein, fetchInputFiles, processInputFile,
} from "@/lib/atrApi";

export function AtrDeliveriesPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [, setLocation] = useLocation();
  const { data: deliveries } = useQuery({ queryKey: ["atr", "deliveries"], queryFn: fetchDeliveries });
  const { data: input } = useQuery({ queryKey: ["atr", "input-files"], queryFn: fetchInputFiles });
  const [busy, setBusy] = useState(false);
  const [picked, setPicked] = useState("");

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

  return (
    <div className="max-w-5xl mx-auto px-6 py-6">
      <h1 className="text-xl font-semibold mb-4">{t("atr.deliveries.heading")}</h1>
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <label className="px-3 py-2 border rounded cursor-pointer">
          {t("atr.deliveries.upload")}
          <input type="file" accept=".pdf" className="hidden" disabled={busy}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); }} />
        </label>
        {input?.configured && (
          <div className="flex items-center gap-2">
            <select className="border rounded px-2 py-2" value={picked}
              onChange={(e) => setPicked(e.target.value)} aria-label={t("atr.deliveries.from_folder")}>
              <option value="">{t("atr.deliveries.from_folder")}</option>
              {input.files.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
            <button className="px-3 py-2 border rounded" disabled={!picked || busy}
              onClick={onProcess}>{t("atr.deliveries.process")}</button>
          </div>
        )}
      </div>
      <table className="w-full text-sm">
        <thead><tr className="text-left border-b">
          <th className="py-2">{t("atr.deliveries.col.source")}</th>
          <th>{t("atr.deliveries.col.ba")}</th>
          <th>{t("atr.deliveries.col.status")}</th>
          <th>{t("atr.deliveries.col.created")}</th><th /></tr></thead>
        <tbody>
          {(deliveries ?? []).map((d) => (
            <tr key={d.id} className="border-b" data-testid={`atr-delivery-${d.id}`}>
              <td className="py-1">{d.source_filename}</td>
              <td>{d.ba_auftrag}</td>
              <td>{d.status}</td>
              <td>{new Date(d.created_at).toLocaleString()}</td>
              <td><button className="text-blue-600"
                onClick={() => setLocation(`/atr/deliveries/${d.id}`)}>{t("atr.deliveries.open")}</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
