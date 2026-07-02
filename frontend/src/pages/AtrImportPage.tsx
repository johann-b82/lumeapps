// frontend/src/pages/AtrImportPage.tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import {
  atrImportPreview, atrImportCommit, type AtrImportPreview,
} from "@/lib/atrApi";

export function AtrImportPage() {
  const { t } = useTranslation();
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<AtrImportPreview[] | null>(null);
  const [updateTemplate, setUpdateTemplate] = useState(false);
  const [setStructure, setSetStructure] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onPreview() {
    if (!files.length) return;
    setBusy(true);
    try {
      setPreviews(await atrImportPreview(files));
    } catch (e) { toast.error(String(e)); } finally { setBusy(false); }
  }

  async function onCommit() {
    setBusy(true);
    try {
      const res = await atrImportCommit(files, {
        update_template: updateTemplate, set_structure: setStructure,
      });
      const created = res.reduce((s, r) => s + r.created, 0);
      const updated = res.reduce((s, r) => s + r.updated, 0);
      toast.success(`${t("atr.import.commit")}: +${created} / ~${updated}`);
      setPreviews(null); setFiles([]);
    } catch (e) { toast.error(String(e)); } finally { setBusy(false); }
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-6">
      <h1 className="text-xl font-semibold mb-4">{t("atr.import.heading")}</h1>
      <input
        type="file" accept=".xlsx" multiple
        aria-label={t("atr.import.choose")}
        onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
      />
      <button className="ml-3 px-3 py-1 border rounded" disabled={!files.length || busy}
        onClick={onPreview}>{t("atr.import.preview")}</button>

      {previews && (
        <div className="mt-6 space-y-6">
          {previews.map((pv) => (
            <div key={pv.source_filename} className="border rounded p-4">
              <div className="font-medium mb-2">{pv.source_filename}</div>
              <div className="text-sm mb-2">
                <span className="text-green-600 mr-3">{t("atr.import.new")}: {pv.new_count}</span>
                <span className="text-amber-600 mr-3">{t("atr.import.updated")}: {pv.updated_count}</span>
                <span className="text-muted-foreground">{t("atr.import.unchanged")}: {pv.unchanged_count}</span>
              </div>
              {pv.warnings.length > 0 && (
                <ul className="text-xs text-red-600 mb-2" data-testid="atr-warnings">
                  {pv.warnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              )}
              <table className="w-full text-xs">
                <tbody>
                  {pv.parts.map((p) => (
                    <tr key={p.part_number_norm} data-status={p.status}>
                      <td className="font-mono pr-2">{p.part_number}</td>
                      <td className="pr-2">{p.part_name}</td>
                      <td className="pr-2">{p.default_weight_kg}</td>
                      <td className={p.status === "new" ? "text-green-600"
                        : p.status === "updated" ? "text-amber-600" : "text-muted-foreground"}>
                        {t(`atr.import.${p.status}`)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={updateTemplate}
              onChange={(e) => setUpdateTemplate(e.target.checked)} />
            {t("atr.import.update_template")}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={setStructure}
              onChange={(e) => setSetStructure(e.target.checked)} />
            {t("atr.import.set_structure")}
          </label>
          <button className="px-4 py-2 bg-blue-600 text-white rounded" disabled={busy}
            onClick={onCommit}>{t("atr.import.commit")}</button>
        </div>
      )}
    </div>
  );
}
