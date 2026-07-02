// frontend/src/pages/AtrSettingsPage.tsx
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  fetchSettings, updateSettings, testAtrFileserver,
  type Settings, type SettingsUpdatePayload,
} from "@/lib/api";

export function AtrSettingsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["settings"], queryFn: fetchSettings });
  const [d, setD] = useState<Partial<Settings>>({});
  const [pw, setPw] = useState("");
  useEffect(() => { if (data) setD(data); }, [data]);

  async function save() {
    if (!data) return;
    const body: SettingsUpdatePayload = {
      color_primary: data.color_primary, color_accent: data.color_accent,
      color_background: data.color_background, color_foreground: data.color_foreground,
      color_muted: data.color_muted, color_destructive: data.color_destructive,
      app_name: data.app_name,
      atr_smb_host: d.atr_smb_host ?? null, atr_smb_share: d.atr_smb_share ?? null,
      atr_smb_domain: d.atr_smb_domain ?? null, atr_smb_user: d.atr_smb_user ?? null,
      atr_input_path: d.atr_input_path ?? null, atr_output_path: d.atr_output_path ?? null,
      atr_archive_path: d.atr_archive_path ?? null,
      atr_scan_interval_s: Number(d.atr_scan_interval_s ?? 0),
      atr_auto_mode: !!d.atr_auto_mode,
      ...(pw ? { atr_smb_password: pw } : {}),
    };
    try {
      await updateSettings(body);
      toast.success(t("atr.fileserver.save")); setPw("");
      qc.invalidateQueries({ queryKey: ["settings"] });
    } catch (e) { toast.error(String(e)); }
  }
  async function test() {
    try {
      const r = await testAtrFileserver();
      r.ok ? toast.success(t("atr.fileserver.test_ok")) : toast.error(r.error ?? "failed");
    } catch (e) { toast.error(String(e)); }
  }

  if (!data) return <div className="p-6">…</div>;
  const text = (k: keyof Settings, label: string) => (
    <label className="flex flex-col text-sm">
      <span className="text-muted-foreground">{t(label)}</span>
      <input className="border rounded px-2 py-1" value={(d[k] as string) ?? ""}
        onChange={(e) => setD((s) => ({ ...s, [k]: e.target.value }))} />
    </label>
  );

  return (
    <div className="max-w-2xl mx-auto px-6 py-6">
      <h1 className="text-xl font-semibold mb-4">{t("atr.fileserver.heading")}</h1>
      <div className="grid grid-cols-2 gap-3">
        {text("atr_smb_host", "atr.fileserver.host")}
        {text("atr_smb_share", "atr.fileserver.share")}
        {text("atr_smb_domain", "atr.fileserver.domain")}
        {text("atr_smb_user", "atr.fileserver.user")}
        <label className="flex flex-col text-sm">
          <span className="text-muted-foreground">{t("atr.fileserver.password")}</span>
          <input type="password" className="border rounded px-2 py-1" value={pw}
            placeholder={data.atr_smb_has_password ? t("atr.fileserver.password_set") : ""}
            onChange={(e) => setPw(e.target.value)} />
        </label>
        {text("atr_input_path", "atr.fileserver.input_path")}
        {text("atr_output_path", "atr.fileserver.output_path")}
        {text("atr_archive_path", "atr.fileserver.archive_path")}
        <label className="flex flex-col text-sm">
          <span className="text-muted-foreground">{t("atr.fileserver.interval")}</span>
          <input type="number" className="border rounded px-2 py-1"
            value={String(d.atr_scan_interval_s ?? 0)}
            onChange={(e) => setD((s) => ({ ...s, atr_scan_interval_s: Number(e.target.value) }))} />
        </label>
        <label className="flex items-center gap-2 text-sm mt-5">
          <input type="checkbox" checked={!!d.atr_auto_mode}
            onChange={(e) => setD((s) => ({ ...s, atr_auto_mode: e.target.checked }))} />
          {t("atr.fileserver.auto_mode")}
        </label>
      </div>
      <div className="mt-4 flex gap-3">
        <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={save}>{t("atr.fileserver.save")}</button>
        <button className="px-4 py-2 border rounded" onClick={test}>{t("atr.fileserver.test")}</button>
      </div>
    </div>
  );
}
