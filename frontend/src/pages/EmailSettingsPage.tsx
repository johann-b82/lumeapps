// frontend/src/pages/EmailSettingsPage.tsx
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  fetchSettings, updateSettings, sendTestEmail,
  startDelegatedLogin, pollDelegatedLogin, disconnectDelegatedLogin,
  type Settings, type SettingsUpdatePayload, type DeviceCodeStart,
} from "@/lib/api";

type Mode = "app" | "delegated";

export function EmailSettingsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["settings"], queryFn: fetchSettings });
  const [d, setD] = useState<Partial<Settings>>({});
  const [secret, setSecret] = useState("");
  const [testTo, setTestTo] = useState("");
  const [device, setDevice] = useState<DeviceCodeStart | null>(null);
  const [signingIn, setSigningIn] = useState(false);
  const pollTimer = useRef<number | null>(null);
  useEffect(() => { if (data) setD(data); }, [data]);
  useEffect(() => () => { if (pollTimer.current) window.clearTimeout(pollTimer.current); }, []);

  const mode: Mode = (d.email_auth_mode as Mode) ?? "app";

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
      email_auth_mode: mode,
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

  async function beginSignIn() {
    if (!data?.email_tenant_id || !data?.email_client_id) {
      toast.error(t("email.settings.delegated.save_first")); return;
    }
    try {
      const start = await startDelegatedLogin();
      setDevice(start);
      setSigningIn(true);
      schedulePoll(start.device_code, start.interval);
    } catch (e) { toast.error(String(e)); }
  }

  function schedulePoll(deviceCode: string, intervalSec: number) {
    pollTimer.current = window.setTimeout(async () => {
      try {
        const r = await pollDelegatedLogin(deviceCode);
        if (r.status === "pending") { schedulePoll(deviceCode, intervalSec); return; }
        setSigningIn(false); setDevice(null);
        if (r.status === "complete") {
          toast.success(t("email.settings.delegated.connected", { account: r.account ?? "" }));
          qc.invalidateQueries({ queryKey: ["settings"] });
        } else {
          toast.error(r.error ?? "failed");
        }
      } catch (e) { setSigningIn(false); setDevice(null); toast.error(String(e)); }
    }, Math.max(1, intervalSec) * 1000);
  }

  async function disconnect() {
    try {
      await disconnectDelegatedLogin();
      toast.success(t("email.settings.delegated.disconnected"));
      qc.invalidateQueries({ queryKey: ["settings"] });
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

      {/* Mode selector */}
      <div className="mb-4">
        <span className="text-sm text-muted-foreground">{t("email.settings.mode")}</span>
        <div className="flex gap-4 mt-1">
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="email_mode" checked={mode === "app"}
              onChange={() => setD((s) => ({ ...s, email_auth_mode: "app" }))} />
            {t("email.settings.mode_app")}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="email_mode" checked={mode === "delegated"}
              onChange={() => setD((s) => ({ ...s, email_auth_mode: "delegated" }))} />
            {t("email.settings.mode_delegated")}
          </label>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {mode === "app" ? t("email.settings.mode_app_hint") : t("email.settings.mode_delegated_hint")}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {text("email_tenant_id", "email.settings.tenant_id")}
        {text("email_client_id", "email.settings.client_id")}
        {mode === "app" && (
          <>
            <label className="flex flex-col text-sm">
              <span className="text-muted-foreground">{t("email.settings.client_secret")}</span>
              <input type="password" className="border rounded px-2 py-1" value={secret}
                placeholder={data.email_has_secret ? t("email.settings.secret_set") : ""}
                onChange={(e) => setSecret(e.target.value)} />
            </label>
            {text("email_sender_address", "email.settings.sender_address")}
            {text("email_sender_name", "email.settings.sender_name")}
          </>
        )}
        <label className="flex items-center gap-2 text-sm mt-1">
          <input type="checkbox" checked={!!d.email_enabled}
            onChange={(e) => setD((s) => ({ ...s, email_enabled: e.target.checked }))} />
          {t("email.settings.enabled")}
        </label>
      </div>
      <div className="mt-4 flex gap-3">
        <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={save}>{t("email.settings.save")}</button>
      </div>

      {/* Delegated sign-in block */}
      {mode === "delegated" && (
        <div className="mt-6 rounded border p-4">
          <h2 className="text-base font-semibold mb-2">{t("email.settings.delegated.heading")}</h2>
          {data.email_delegated_connected ? (
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm">
                {t("email.settings.delegated.connected", { account: data.email_delegated_account ?? "" })}
              </span>
              <button className="px-3 py-1.5 border rounded text-sm" onClick={disconnect}>
                {t("email.settings.delegated.disconnect")}
              </button>
            </div>
          ) : signingIn && device ? (
            <div className="text-sm space-y-2">
              <p>{t("email.settings.delegated.instructions")}</p>
              <p>
                <a href={device.verification_uri} target="_blank" rel="noreferrer"
                  className="text-blue-600 underline">{device.verification_uri}</a>
              </p>
              <p className="text-lg font-mono font-semibold tracking-widest">{device.user_code}</p>
              <p className="text-muted-foreground">{t("email.settings.delegated.waiting")}</p>
            </div>
          ) : (
            <button className="px-4 py-2 border rounded" onClick={beginSignIn}>
              {t("email.settings.delegated.sign_in")}
            </button>
          )}
        </div>
      )}

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
