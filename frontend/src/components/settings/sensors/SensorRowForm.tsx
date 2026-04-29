import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Trash2 } from "lucide-react";
import type { SensorDraftRow } from "@/hooks/useSensorDraft";
import { SensorProbeButton } from "./SensorProbeButton";
import { DeleteDialog } from "@/components/ui/delete-dialog";

export interface SensorRowFormProps {
  row: SensorDraftRow;
  onChange: (patch: Partial<SensorDraftRow>) => void;
  onRemove: () => void;
}

/**
 * Phase 40-01 — one sensor row editor (SEN-ADM-02 / SEN-ADM-03).
 *
 * Layout: responsive grid. Community is password-type + write-only;
 * shows "stored — leave blank to keep" hint on existing rows until
 * the user types.
 */
export function SensorRowForm({ row, onChange, onRemove }: SensorRowFormProps) {
  const { t } = useTranslation();
  const communityPlaceholder =
    row.hasStoredCommunity && !row.communityDirty ? "••••••" : "";
  const isMarkedForDelete = row._markedForDelete;
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false);

  const handleRemove = () => {
    // Unsaved new rows (id === null) drop immediately — no server state
    // to warn about. Existing rows go through the canonical DeleteDialog.
    if (row.id === null) {
      onRemove();
      return;
    }
    setRemoveDialogOpen(true);
  };

  const handleRemoveConfirm = () => {
    setRemoveDialogOpen(false);
    onRemove();
  };

  return (
    <div
      className={`rounded-md border border-border bg-card p-4 space-y-4 ${
        isMarkedForDelete ? "opacity-50" : ""
      }`}
    >
      {isMarkedForDelete && (
        <p className="text-xs text-destructive">
          {t("sensors.admin.remove_confirm.body", { name: row.name })}
        </p>
      )}

      {/* Row 1: name | host | port */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div className="flex flex-col gap-2 md:col-span-2">
          <Label htmlFor={`sensor-${row._localId}-name`} className="text-sm font-medium">
            {t("sensors.admin.fields.name")}
          </Label>
          <Input
            id={`sensor-${row._localId}-name`}
            value={row.name}
            placeholder={t("sensors.admin.fields.name.placeholder")}
            onChange={(e) => onChange({ name: e.target.value })}
            disabled={isMarkedForDelete}
          />
        </div>
        <div className="flex flex-col gap-2 md:col-span-2">
          <Label htmlFor={`sensor-${row._localId}-host`} className="text-sm font-medium">
            {t("sensors.admin.fields.host")}
          </Label>
          <Input
            id={`sensor-${row._localId}-host`}
            value={row.host}
            placeholder={t("sensors.admin.fields.host.placeholder")}
            onChange={(e) => onChange({ host: e.target.value })}
            disabled={isMarkedForDelete}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor={`sensor-${row._localId}-port`} className="text-sm font-medium">
            {t("sensors.admin.fields.port")}
          </Label>
          <Input
            id={`sensor-${row._localId}-port`}
            type="number"
            min={1}
            max={65535}
            value={row.port}
            onChange={(e) => onChange({ port: Number(e.target.value) })}
            disabled={isMarkedForDelete}
          />
        </div>
      </div>

      {/* Row 2: community */}
      <div className="flex flex-col gap-2 max-w-md">
        <Label htmlFor={`sensor-${row._localId}-community`} className="text-sm font-medium">
          {t("sensors.admin.fields.community")}
        </Label>
        <Input
          id={`sensor-${row._localId}-community`}
          type="password"
          value={row.community}
          placeholder={communityPlaceholder}
          onChange={(e) =>
            onChange({ community: e.target.value, communityDirty: true })
          }
          disabled={isMarkedForDelete}
          autoComplete="new-password"
        />
        {row.hasStoredCommunity && !row.communityDirty && (
          <p className="text-xs text-muted-foreground">
            {t("sensors.admin.fields.community.saved_hint")}
          </p>
        )}
      </div>

      {/* Row 3: temperature_oid | humidity_oid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="flex flex-col gap-2">
          <Label
            htmlFor={`sensor-${row._localId}-temp-oid`}
            className="text-sm font-medium"
          >
            {t("sensors.admin.fields.temperature_oid")}
          </Label>
          <Input
            id={`sensor-${row._localId}-temp-oid`}
            value={row.temperature_oid}
            onChange={(e) => onChange({ temperature_oid: e.target.value })}
            disabled={isMarkedForDelete}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label
            htmlFor={`sensor-${row._localId}-hum-oid`}
            className="text-sm font-medium"
          >
            {t("sensors.admin.fields.humidity_oid")}
          </Label>
          <Input
            id={`sensor-${row._localId}-hum-oid`}
            value={row.humidity_oid}
            onChange={(e) => onChange({ humidity_oid: e.target.value })}
            disabled={isMarkedForDelete}
          />
        </div>
      </div>

      {/* Row 4: temp_scale | humidity_scale | enabled */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
        <div className="flex flex-col gap-2">
          <Label
            htmlFor={`sensor-${row._localId}-temp-scale`}
            className="text-sm font-medium"
          >
            {t("sensors.admin.fields.temperature_scale")}
          </Label>
          <Input
            id={`sensor-${row._localId}-temp-scale`}
            type="number"
            step="0.1"
            min="0"
            value={row.temperature_scale}
            onChange={(e) => onChange({ temperature_scale: e.target.value })}
            disabled={isMarkedForDelete}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label
            htmlFor={`sensor-${row._localId}-hum-scale`}
            className="text-sm font-medium"
          >
            {t("sensors.admin.fields.humidity_scale")}
          </Label>
          <Input
            id={`sensor-${row._localId}-hum-scale`}
            type="number"
            step="0.1"
            min="0"
            value={row.humidity_scale}
            onChange={(e) => onChange({ humidity_scale: e.target.value })}
            disabled={isMarkedForDelete}
          />
        </div>
        <div className="flex items-center gap-2 pb-2">
          <Checkbox
            id={`sensor-${row._localId}-enabled`}
            checked={row.enabled}
            onCheckedChange={(next) => onChange({ enabled: Boolean(next) })}
            disabled={isMarkedForDelete}
          />
          <Label
            htmlFor={`sensor-${row._localId}-enabled`}
            className="text-sm font-medium"
          >
            {t("sensors.admin.fields.enabled")}
          </Label>
        </div>
      </div>

      {/* Row 5: probe + remove */}
      <div className="flex items-center justify-between gap-4">
        <SensorProbeButton row={row} />
        <Button
          type="button"
          variant="ghost"
          className="text-destructive hover:text-destructive"
          onClick={handleRemove}
          disabled={isMarkedForDelete}
        >
          <Trash2 className="h-4 w-4 mr-1" aria-hidden="true" />
          {t("sensors.admin.remove_sensor")}
        </Button>
      </div>

      <DeleteDialog
        open={removeDialogOpen}
        onOpenChange={setRemoveDialogOpen}
        title={t("sensors.admin.remove_confirm.title")}
        body={t("sensors.admin.remove_confirm.body", {
          name: row.name || "(unnamed)",
        })}
        cancelLabel={t("sensors.admin.remove_confirm.cancel")}
        confirmLabel={t("sensors.admin.remove_confirm.confirm")}
        onConfirm={handleRemoveConfirm}
      />
    </div>
  );
}
