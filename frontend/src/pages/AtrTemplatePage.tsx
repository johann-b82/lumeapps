// frontend/src/pages/AtrTemplatePage.tsx
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  fetchAtrTemplate, updateAtrTemplate, setAtrStructure, type AtrTemplate,
} from "@/lib/atrApi";

const FIELDS: (keyof AtrTemplate)[] = [
  "customer", "ac_programme", "work_package", "purchaser_spec", "atp",
  "supplier_spec", "reference_no", "supplier", "customer_spec", "nscm_code",
  "ata_chapter", "weighing_equipment", "qa_signer_default",
];

export function AtrTemplatePage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["atr", "template"], queryFn: fetchAtrTemplate });
  const [draft, setDraft] = useState<Partial<AtrTemplate>>({});
  useEffect(() => { if (data) setDraft(data); }, [data]);

  async function save() {
    try {
      const body: Partial<AtrTemplate> = {};
      FIELDS.forEach((f) => { (body as Record<string, unknown>)[f] = draft[f] ?? null; });
      await updateAtrTemplate(body);
      toast.success(t("atr.template.save"));
      qc.invalidateQueries({ queryKey: ["atr", "template"] });
    } catch (e) { toast.error(String(e)); }
  }

  async function onStructure(file: File) {
    try {
      await setAtrStructure(file);
      toast.success(t("atr.template.structure"));
      qc.invalidateQueries({ queryKey: ["atr", "template"] });
    } catch (e) { toast.error(String(e)); }
  }

  if (!data) return <div className="p-6">…</div>;
  return (
    <div className="max-w-3xl mx-auto px-6 py-6">
      <h1 className="text-xl font-semibold mb-4">{t("atr.template.heading")}</h1>
      <div className="mb-6 text-sm">
        <span className="font-medium">{t("atr.template.structure")}: </span>
        {data.has_structure ? data.structure_filename : t("atr.template.no_structure")}
        <div className="mt-2">
          <input type="file" accept=".xlsx" aria-label={t("atr.template.upload_structure")}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onStructure(f); }} />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3">
        {FIELDS.map((f) => (
          <label key={f} className="flex flex-col text-sm">
            <span className="text-muted-foreground">{f}</span>
            <input className="border rounded px-2 py-1" value={(draft[f] as string) ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, [f]: e.target.value }))} />
          </label>
        ))}
      </div>
      <button className="mt-4 px-4 py-2 bg-blue-600 text-white rounded" onClick={save}>
        {t("atr.template.save")}
      </button>
    </div>
  );
}
