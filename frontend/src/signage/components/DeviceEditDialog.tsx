import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Toggle } from "@/components/ui/toggle";
import { signageKeys } from "@/lib/queryKeys";
import { signageApi } from "@/signage/lib/signageApi";
import type { SignageDevice } from "@/signage/lib/signageTypes";
import { TagPicker } from "./TagPicker";
import { UnsavedChangesDialog } from "./UnsavedChangesDialog";

// Phase 62 — Calibration fields added (CAL-UI-01..03). Rotation literal
// mirrors backend Literal[0,90,180,270] so the dropdown can't submit an
// unsupported transform. hdmi_mode null = "Auto (use current)" per D-02.
const schema = z.object({
  name: z.string().min(1).max(128),
  tags: z.array(z.string()),
  rotation: z.union([
    z.literal(0),
    z.literal(90),
    z.literal(180),
    z.literal(270),
  ]),
  hdmi_mode: z.string().nullable(),
  audio_enabled: z.boolean(),
});
type FormValues = z.infer<typeof schema>;

export interface DeviceEditDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  device: SignageDevice | null;
}

// Rotation options — rendered as "0°/90°/180°/270°". Values coerced to
// numbers at the Select<->form boundary (base-ui Select values are strings).
const ROTATIONS: ReadonlyArray<0 | 90 | 180 | 270> = [0, 90, 180, 270];

// Sentinel for the Auto HDMI option. Empty-string option value maps to
// `null` in form state so the PATCH body carries null when the operator
// keeps the device on its current mode (D-02).
const HDMI_AUTO_VALUE = "";

/**
 * Edit-device dialog with dirty-guard (SGN-ADM-09 / D-09). Save flow:
 *   1. Resolve tag names → IDs (create-on-submit via signageApi.createTag)
 *   2. PATCH /devices/{id} for name (backend SignageDeviceAdminUpdate is name-only)
 *   3. PUT  /devices/{id}/tags for tag_ids (separate endpoint per devices.py)
 *   4. PATCH /devices/{id}/calibration for rotation/hdmi_mode/audio_enabled
 *      — only the fields that became dirty (Phase 62 CAL-UI-03 partial contract)
 *
 * Dirty-guard: when the user attempts to close the dialog with form.formState.isDirty,
 * the close is intercepted and an UnsavedChangesDialog is shown instead.
 * Discard → reset form + close. Stay → cancel close (UnsavedChangesDialog closes only).
 */
export function DeviceEditDialog({
  open,
  onOpenChange,
  device,
}: DeviceEditDialogProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [unsavedOpen, setUnsavedOpen] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      tags: [],
      rotation: 0,
      hdmi_mode: null,
      audio_enabled: false,
    },
  });

  const { data: allTags = [] } = useQuery({
    queryKey: signageKeys.tags(),
    queryFn: signageApi.listTags,
    staleTime: 60_000,
  });

  // Reset form whenever the device prop changes (dialog reopened on a new row).
  useEffect(() => {
    if (device) {
      const tagById = new Map(allTags.map((tag) => [tag.id, tag.name]));
      const ids = device.tag_ids ?? device.tags?.map((t) => t.id) ?? [];
      form.reset({
        name: device.name,
        tags: ids
          .map((id) => tagById.get(id))
          .filter((n): n is string => typeof n === "string"),
        rotation: device.rotation,
        hdmi_mode: device.hdmi_mode,
        audio_enabled: device.audio_enabled,
      });
    }
  }, [device, allTags, form]);

  // Memoize Toggle segments — otherwise their identity changes every render
  // and Toggle's useLayoutEffect (which depends on `segments`) re-fires,
  // calling setIndicatorStyle with a new object reference each time →
  // infinite render loop under jsdom (and a wasteful extra paint in prod).
  const audioSegments = useMemo(
    () =>
      [
        {
          value: "off" as const,
          label: t("signage.admin.device.calibration.audio_off"),
        },
        {
          value: "on" as const,
          label: t("signage.admin.device.calibration.audio_on"),
        },
      ] as const,
    [t],
  );

  // HDMI options: Auto placeholder + device-reported modes (D-02 — until
  // sidecar heartbeat carries `available_modes`, only Auto is present —
  // CAL-UI-02).
  const hdmiOptions = useMemo(() => {
    const reported = device?.available_modes ?? [];
    return [
      {
        value: HDMI_AUTO_VALUE,
        label: t("signage.admin.device.calibration.hdmi_mode_auto"),
      },
      ...reported.map((m) => ({ value: m, label: m })),
    ];
  }, [device?.available_modes, t]);

  const saveMutation = useMutation({
    mutationFn: async (values: FormValues) => {
      if (!device) throw new Error("no device");
      // Resolve tag names → ids (create unknown tags first).
      const existing = await signageApi.listTags();
      const nameToId = new Map(existing.map((tag) => [tag.name, tag.id]));
      const tagIds: number[] = [];
      for (const name of values.tags) {
        let id = nameToId.get(name);
        if (id === undefined) {
          const created = await signageApi.createTag(name);
          id = created.id;
        }
        tagIds.push(id);
      }
      // Sequence: PATCH name, then PUT tags, then PATCH calibration.
      await signageApi.updateDevice(device.id, { name: values.name });
      await signageApi.replaceDeviceTags(device.id, tagIds);

      // Partial calibration PATCH — send only dirty fields so the backend
      // audit trail stays minimal and SSE fanout doesn't fire on no-op.
      const dirty = form.formState.dirtyFields;
      const calibBody: Partial<{
        rotation: 0 | 90 | 180 | 270;
        hdmi_mode: string | null;
        audio_enabled: boolean;
      }> = {};
      if (dirty.rotation) calibBody.rotation = values.rotation;
      if (dirty.hdmi_mode) calibBody.hdmi_mode = values.hdmi_mode;
      if (dirty.audio_enabled) calibBody.audio_enabled = values.audio_enabled;
      if (Object.keys(calibBody).length > 0) {
        await signageApi.updateDeviceCalibration(device.id, calibBody);
      }
    },
    onSuccess: () => {
      // Phase 70-04 (D-05a): namespaced cache keys — name PATCH and tag-map
      // mutations both can flip the resolved cell. Invalidate both Directus
      // device list/row and the per-device FastAPI resolved cache.
      queryClient.invalidateQueries({ queryKey: signageKeys.devices() });
      queryClient.invalidateQueries({ queryKey: ["directus", "signage_devices"] });
      if (device) {
        queryClient.invalidateQueries({
          queryKey: ["directus", "signage_devices", device.id],
        });
        queryClient.invalidateQueries({
          queryKey: ["fastapi", "resolved", device.id],
        });
      }
      queryClient.invalidateQueries({ queryKey: signageKeys.tags() });
      toast.success(t("signage.admin.device.calibration.saved"));
      form.reset(form.getValues());
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const detail = err instanceof Error ? err.message : String(err);
      toast.error(t("signage.admin.device.save_error", { detail }));
    },
  });

  // Intercept close attempts when the form is dirty: route through unsaved guard.
  function handleOpenChange(next: boolean) {
    if (!next && form.formState.isDirty) {
      setUnsavedOpen(true);
      return;
    }
    onOpenChange(next);
  }

  function discardAndClose() {
    form.reset();
    setUnsavedOpen(false);
    onOpenChange(false);
  }

  return (
    <>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("signage.admin.device.edit_title")}</DialogTitle>
            <DialogDescription>
              {device?.name ?? ""}
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={form.handleSubmit((values) => saveMutation.mutate(values))}
            className="flex flex-col gap-4"
          >
            <div className="flex flex-col gap-2">
              <Label htmlFor="device-edit-name">
                {t("signage.admin.pair.name_label")}
              </Label>
              <Input
                id="device-edit-name"
                {...form.register("name")}
                aria-invalid={!!form.formState.errors.name}
                autoComplete="off"
              />
              {form.formState.errors.name && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.name.message}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <Label>{t("signage.admin.pair.tags_label")}</Label>
              <Controller
                name="tags"
                control={form.control}
                render={({ field }) => (
                  <TagPicker
                    value={field.value}
                    onChange={field.onChange}
                    placeholder={t("signage.admin.pair.tags_placeholder")}
                    ariaLabel={t("signage.admin.pair.tags_label")}
                  />
                )}
              />
            </div>

            {/* Phase 62 — Calibration section (CAL-UI-01..03). */}
            <div className="flex flex-col gap-3 border-t pt-4">
              <h3 className="text-sm font-medium">
                {t("signage.admin.device.calibration.title")}
              </h3>

              <div className="flex flex-col gap-2">
                <Label htmlFor="device-edit-rotation">
                  {t("signage.admin.device.calibration.rotation_label")}
                </Label>
                <Controller
                  name="rotation"
                  control={form.control}
                  render={({ field }) => (
                    <Select
                      value={String(field.value)}
                      onValueChange={(v) =>
                        field.onChange(Number(v) as 0 | 90 | 180 | 270)
                      }
                    >
                      <SelectTrigger
                        id="device-edit-rotation"
                        aria-label={t(
                          "signage.admin.device.calibration.rotation_label",
                        )}
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ROTATIONS.map((deg) => (
                          <SelectItem key={deg} value={String(deg)}>
                            {deg}°
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="device-edit-hdmi">
                  {t("signage.admin.device.calibration.hdmi_mode_label")}
                </Label>
                <Controller
                  name="hdmi_mode"
                  control={form.control}
                  render={({ field }) => (
                    <Select
                      value={field.value ?? HDMI_AUTO_VALUE}
                      onValueChange={(v) =>
                        field.onChange(v === HDMI_AUTO_VALUE ? null : v)
                      }
                    >
                      <SelectTrigger
                        id="device-edit-hdmi"
                        aria-label={t(
                          "signage.admin.device.calibration.hdmi_mode_label",
                        )}
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {hdmiOptions.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>

              <div className="flex flex-col gap-2">
                <Label>
                  {t("signage.admin.device.calibration.audio_label")}
                </Label>
                <Controller
                  name="audio_enabled"
                  control={form.control}
                  render={({ field }) => (
                    <Toggle
                      aria-label={t(
                        "signage.admin.device.calibration.audio_label",
                      )}
                      segments={audioSegments}
                      value={field.value ? "on" : "off"}
                      onChange={(v) => field.onChange(v === "on")}
                    />
                  )}
                />
              </div>
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => handleOpenChange(false)}
                disabled={saveMutation.isPending}
              >
                {t("signage.admin.device.revoke_cancel")}
              </Button>
              <Button type="submit" disabled={saveMutation.isPending}>
                {t("signage.admin.device.edit_title")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <UnsavedChangesDialog
        open={unsavedOpen}
        onOpenChange={setUnsavedOpen}
        onStay={() => setUnsavedOpen(false)}
        onDiscardAndLeave={discardAndClose}
      />
    </>
  );
}
