// frontend/src/pages/EmailSettingsPage.tsx
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  fetchSettings, updateSettings, sendTestEmail,
  type Settings, type SettingsUpdatePayload,
} from "@/lib/api";

export function EmailSettingsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["settings"], queryFn: fetchSettings });
  const [d, setD] = useState<Partial<Settings>>({});
  const [secret, setSecret] = useState("");
  const [testTo, setTestTo] = useState("");
  useEffect(() => { if (data) setD(data); }, [data]);

  async function save() {
    if (!data) return;
    const body: SettingsUpdatePayload = {
      color_primary: data.color_primary, color_accent: data.color_accent,
      color_background: data.color_background, color_foreground: data.color_foreground,
      color_muted: data.color_muted, color_destructive: data.color_destructive,
      app_name: data.app_name,
      email_tenant_id: d.email_tenant_id ?? null,
      email_client_id: d.email_client_id ?? null,
      email_sender_address: d.email_sender_address ?? null,
      email_sender_name: d.email_sender_name ?? null,
      email_enabled: !!d.email_enabled,
      ...(secret ? { email_client_secret: secret } : {}),
    };
    try {
      await updateSettings(body);
      toast.success(t("email.settings.save")); setSecret("");
      qc.invalidateQueries({ queryKey: ["settings"] });
    } catch (e) { toast.error(String(e)); }
  }

  async function test() {
    if (!testTo) { toast.error(t("email.settings.test_no_address")); return; }
    try {
      const r = await sendTestEmail(testTo);
      r.ok ? toast.success(t("email.settings.test_ok")) : toast.error(r.error ?? "failed");
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
      <h1 className="text-xl font-semibold mb-1">{t("email.settings.heading")}</h1>
      <p className="text-sm text-muted-foreground mb-4">{t("email.settings.intro")}</p>
      <div className="grid grid-cols-2 gap-3">
        {text("email_tenant_id", "email.settings.tenant_id")}
        {text("email_client_id", "email.settings.client_id")}
        <label className="flex flex-col text-sm">
          <span className="text-muted-foreground">{t("email.settings.client_secret")}</span>
          <input type="password" className="border rounded px-2 py-1" value={secret}
            placeholder={data.email_has_secret ? t("email.settings.secret_set") : ""}
            onChange={(e) => setSecret(e.target.value)} />
        </label>
        {text("email_sender_address", "email.settings.sender_address")}
        {text("email_sender_name", "email.settings.sender_name")}
        <label className="flex items-center gap-2 text-sm mt-5">
          <input type="checkbox" checked={!!d.email_enabled}
            onChange={(e) => setD((s) => ({ ...s, email_enabled: e.target.checked }))} />
          {t("email.settings.enabled")}
        </label>
      </div>
      <div className="mt-4 flex gap-3">
        <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={save}>{t("email.settings.save")}</button>
      </div>

      <hr className="my-6" />
      <h2 className="text-base font-semibold mb-2">{t("email.settings.test_heading")}</h2>
      <div className="flex items-end gap-3">
        <label className="flex flex-col text-sm flex-1">
          <span className="text-muted-foreground">{t("email.settings.test_to")}</span>
          <input type="email" className="border rounded px-2 py-1" value={testTo}
            placeholder="name@firma.de"
            onChange={(e) => setTestTo(e.target.value)} />
        </label>
        <button className="px-4 py-2 border rounded" onClick={test}>{t("email.settings.test")}</button>
      </div>
    </div>
  );
}
