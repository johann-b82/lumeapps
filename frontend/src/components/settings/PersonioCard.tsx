import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, CheckCircle2, PlugZap, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CheckboxList } from "@/components/settings/CheckboxList";
import type { CheckboxOption } from "@/components/settings/CheckboxList";
import { fetchPersonioOptions, testPersonioConnection, triggerSync } from "@/lib/api";
import { AdminOnly } from "@/auth/AdminOnly";
import { syncKeys, hrKpiKeys } from "@/lib/queryKeys";
import type { DraftFields } from "@/hooks/useSettingsDraft";

interface PersonioCardProps {
  draft: DraftFields;
  setField: <K extends keyof DraftFields>(field: K, value: DraftFields[K]) => void;
  /** True when the backend reports Personio credentials are stored (personio_has_credentials). */
  hasCredentials: boolean;
  /** When true, render without a Card wrapper — as a subsection inside a parent card. */
  embedded?: boolean;
}

/**
 * Personio settings section.
 *
 * - Credential inputs are masked (type="password"), write-only.
 * - Connection test uses local state — does not affect the draft.
 * - Absence type and department dropdowns are populated live from the
 *   GET /api/settings/personio-options endpoint (staleTime: 0 per D-09).
 *   They are disabled until credentials exist (D-10).
 * - All fields are saved via the existing shared Speichern button (D-13).
 */
export function PersonioCard({ draft, setField, hasCredentials, embedded = false }: PersonioCardProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const INTERVAL_OPTIONS: Array<{ value: 0 | 1 | 6 | 24; label: string }> = [
    { value: 0, label: t("settings.personio.sync_interval.manual") },
    { value: 1, label: t("settings.personio.sync_interval.hourly") },
    { value: 6, label: t("settings.personio.sync_interval.every6h") },
    { value: 24, label: t("settings.personio.sync_interval.daily") },
  ];

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    error: string | null;
  } | null>(null);

  const [syncFeedback, setSyncFeedback] = useState<"idle" | "success" | "error">("idle");
  const [syncError, setSyncError] = useState<string | null>(null);
  const syncMutation = useMutation({
    mutationFn: triggerSync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: syncKeys.meta() });
      queryClient.invalidateQueries({ queryKey: hrKpiKeys.all() });
      setSyncFeedback("success");
      setTimeout(() => setSyncFeedback("idle"), 3000);
    },
    onError: (err: Error) => {
      setSyncFeedback("error");
      setSyncError(err.message);
    },
  });

  // Fetch Personio options only when credentials are configured (D-09)
  const { data: options, isLoading: optionsLoading } = useQuery({
    queryKey: ["personio-options"],
    queryFn: fetchPersonioOptions,
    staleTime: 0,      // always fresh per D-09
    enabled: hasCredentials,
  });

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testPersonioConnection();
      setTestResult(result);
    } catch (err) {
      setTestResult({
        success: false,
        error: err instanceof Error ? err.message : t("settings.personio.test_connection.error_fallback"),
      });
    } finally {
      setTesting(false);
    }
  };

  const dropdownsDisabled = !hasCredentials || optionsLoading || !!options?.error;
  const noCredentialsHint = !hasCredentials ? t("settings.personio.credentials.configure_hint") : null;
  const optionsError = options?.error ?? null;

  const body = (
    <div className="space-y-8">
        {/* Credentials row: Client-ID | Client-Secret | Sync-Intervall (narrow, right) */}
        <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_12rem] gap-x-6 gap-y-6">
          {/* Client-ID */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="personio-client-id" className="text-sm font-medium">
              {t("settings.personio.client_id.label")}
            </Label>
            <Input
              id="personio-client-id"
              type="password"
              autoComplete="new-password"
              value={draft.personio_client_id}
              onChange={(e) => setField("personio_client_id", e.target.value)}
              placeholder={t("settings.personio.client_id.placeholder")}
            />
            {hasCredentials && !draft.personio_client_id && (
              <p className="text-xs text-muted-foreground">
                {t("settings.personio.client_id.saved_hint")}
              </p>
            )}
          </div>

          {/* Client-Secret */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="personio-client-secret" className="text-sm font-medium">
              {t("settings.personio.client_secret.label")}
            </Label>
            <Input
              id="personio-client-secret"
              type="password"
              autoComplete="new-password"
              value={draft.personio_client_secret}
              onChange={(e) => setField("personio_client_secret", e.target.value)}
              placeholder={t("settings.personio.client_secret.placeholder")}
            />
            {hasCredentials && !draft.personio_client_secret && (
              <p className="text-xs text-muted-foreground">
                {t("settings.personio.client_secret.saved_hint")}
              </p>
            )}
          </div>

          {/* Sync-Intervall (narrow, far right) */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="personio-sync-interval" className="text-sm font-medium">
              {t("settings.personio.sync_interval.label")}
            </Label>
            <Select
              value={String(draft.personio_sync_interval_h)}
              onValueChange={(v: string) =>
                setField(
                  "personio_sync_interval_h",
                  Number(v) as 0 | 1 | 6 | 24,
                )
              }
            >
              <SelectTrigger id="personio-sync-interval">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {INTERVAL_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={String(opt.value)}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Test connection + Refresh (above separator) */}
        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={testing || (!hasCredentials && !draft.personio_client_id)}
              onClick={handleTestConnection}
            >
              {testing ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <PlugZap className="h-4 w-4 mr-1" />
              )}
              {testing ? t("settings.personio.test_connection.testing") : t("settings.personio.test_connection.button")}
            </Button>
            <AdminOnly>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setSyncFeedback("idle");
                  setSyncError(null);
                  syncMutation.mutate();
                }}
                disabled={syncMutation.isPending || !hasCredentials}
              >
                {syncMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    {t("hr.sync.button")}
                  </>
                ) : syncFeedback === "success" ? (
                  <>
                    <CheckCircle2 className="h-4 w-4 mr-1 text-[var(--color-success)]" />
                    {t("hr.sync.success")}
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-4 w-4 mr-1" />
                    {t("hr.sync.button")}
                  </>
                )}
              </Button>
            </AdminOnly>
          </div>
          {testResult !== null && (
            <p
              className={
                testResult.success
                  ? "text-sm text-[var(--color-success)]"
                  : "text-sm text-destructive"
              }
            >
              {testResult.success
                ? t("settings.personio.test_connection.success")
                : (testResult.error ?? t("settings.personio.test_connection.failure"))}
            </p>
          )}
          {syncFeedback === "error" && (
            <p className="text-xs text-destructive">
              {t("hr.sync.error")}
              {syncError ? `: ${syncError}` : ""}
            </p>
          )}
        </div>

        <hr className="border-border" />

        <div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-6">

        {/* Krankheitstyp (absence type) — multi-select checkbox list per UI-01 */}
        <CheckboxList
          id="personio-sick-leave"
          label={t("settings.personio.sick_leave_type.label")}
          options={(options?.absence_types ?? []).map((at): CheckboxOption => ({
            value: String(at.id),
            label: at.name,
          }))}
          selected={draft.personio_sick_leave_type_id.map(String)}
          onChange={(vals) =>
            setField("personio_sick_leave_type_id", vals.map(Number))
          }
          disabled={dropdownsDisabled}
          loading={hasCredentials && optionsLoading}
          hint={noCredentialsHint ?? optionsError}
        />

        {/* Produktions-Abteilung — multi-select checkbox list per UI-01 */}
        <CheckboxList
          id="personio-dept"
          label={t("settings.personio.production_dept.label")}
          options={(options?.departments ?? []).map((dept): CheckboxOption => ({
            value: dept,
            label: dept,
          }))}
          selected={draft.personio_production_dept}
          onChange={(vals) => setField("personio_production_dept", vals)}
          disabled={dropdownsDisabled}
          loading={hasCredentials && optionsLoading}
          hint={noCredentialsHint ?? optionsError}
        />

        {/* Skill-Attribut-Key — multi-select checkbox list per UI-01, D-01 */}
        <CheckboxList
          id="personio-skill-key"
          label={t("settings.personio.skill_attr_key.label")}
          options={(options?.skill_attributes ?? []).map((key): CheckboxOption => ({
            value: key,
            label: key,
          }))}
          selected={draft.personio_skill_attr_key}
          onChange={(vals) => setField("personio_skill_attr_key", vals)}
          disabled={dropdownsDisabled}
          loading={hasCredentials && optionsLoading}
          hint={noCredentialsHint ?? optionsError}
        />

          </div>
        </div>
    </div>
  );

  if (embedded) {
    return (
      <section className="space-y-4">
        <h3 className="text-base font-semibold">
          {t("settings.personio.title")}
        </h3>
        {body}
      </section>
    );
  }

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="text-xl font-semibold">{t("settings.personio.title")}</CardTitle>
      </CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  );
}
