import { useTranslation } from "react-i18next";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { DraftFields } from "@/hooks/useSettingsDraft";

interface WorldCupSettingsCardProps {
  draft: DraftFields;
  setField: <K extends keyof DraftFields>(field: K, value: DraftFields[K]) => void;
  /** From Settings.worldcup_has_api_key — the key itself is write-only. */
  hasApiKey: boolean;
}

export function WorldCupSettingsCard({ draft, setField, hasApiKey }: WorldCupSettingsCardProps) {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl font-semibold">{t("settings.worldcup.title")}</CardTitle>
        <p className="text-sm text-muted-foreground">{t("settings.worldcup.description")}</p>
      </CardHeader>
      <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="worldcup-api-key" className="text-sm font-medium">
            {t("settings.worldcup.api_key.label")}
          </Label>
          <Input
            id="worldcup-api-key"
            type="password"
            autoComplete="new-password"
            value={draft.worldcup_api_key}
            onChange={(e) => setField("worldcup_api_key", e.target.value)}
            placeholder={t("settings.worldcup.api_key.placeholder")}
          />
          {hasApiKey && !draft.worldcup_api_key && (
            <p className="text-xs text-muted-foreground">
              {t("settings.worldcup.api_key.saved_hint")}
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="worldcup-refresh" className="text-sm font-medium">
            {t("settings.worldcup.refresh.label")}
          </Label>
          <Input
            id="worldcup-refresh"
            type="number"
            min={30}
            max={3600}
            value={String(draft.worldcup_refresh_seconds)}
            onChange={(e) => {
              const num = parseInt(e.target.value, 10);
              if (!isNaN(num)) setField("worldcup_refresh_seconds", num);
            }}
          />
        </div>
      </CardContent>
    </Card>
  );
}
