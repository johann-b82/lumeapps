import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { signageKeys } from "@/lib/queryKeys";
import { signageApi } from "@/signage/lib/signageApi";
import type {
  SignageSchedule,
  SignageScheduleCreate,
  SignageScheduleUpdate,
} from "@/signage/lib/signageTypes";
import { WeekdayCheckboxRow } from "@/signage/components/WeekdayCheckboxRow";
import {
  hhmmFromString,
  hhmmToString,
  weekdayMaskFromArray,
  weekdayMaskToArray,
} from "@/signage/lib/scheduleAdapters";

/**
 * Phase 52 Plan 02 — create/edit schedule dialog.
 *
 * Validation decision tree (D-11/D-12, consolidated with D-07):
 *   1. playlist required -> error.playlist_required
 *   2. >=1 weekday        -> error.weekdays_required
 *   3. time branch (replaces former 3-rule chain):
 *        startN/endN null -> error.time_format
 *        startN === endN  -> error.start_equals_end
 *        startN > endN    -> error.midnight_span  (D-07 — same-day reversal
 *                                                  is ALWAYS treated as a
 *                                                  midnight span; the
 *                                                  error.start_after_end
 *                                                  key is reserved for
 *                                                  backend-error surfacing
 *                                                  via error.save_failed,
 *                                                  NEVER emitted by the
 *                                                  client validator).
 *        startN < endN    -> valid window (no error)
 *   4. priority < 0 is clamped to 0 on submit (D-08 — no distinct key)
 *
 * Timing (D-11): full validate on submit; per-field + cross-field revalidate
 * on blur for touched fields only. Untouched fields stay neutral before first
 * submit attempt.
 */
export interface ScheduleEditDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** null or undefined = create mode; object = edit mode. */
  schedule?: SignageSchedule | null;
}

type FieldName = "playlist" | "weekdays" | "time" | "priority";
type Errors = Partial<Record<FieldName, string>>;
type Touched = Partial<Record<FieldName, boolean>>;

const INIT_WEEKDAYS: boolean[] = [false, false, false, false, false, false, false];

/**
 * Phase 68 Plan 05 (MIG-SIGN-02): Detects the Directus Flow validation error
 * (code `schedule_end_before_start`) thrown server-side when start_hhmm >= end_hhmm
 * is written outside the dialog's client-side validators (e.g. via the Directus
 * Data Model UI or REST). Matches both the JSON-stringified Error.message shape
 * (Plan 02 throws `new Error(JSON.stringify({ code }))`) AND the canonical
 * Directus SDK error shape `{ errors: [{ extensions: { code } }] }`.
 */
function isScheduleEndBeforeStartError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  if (msg.includes("schedule_end_before_start")) return true;
  if (err && typeof err === "object" && "errors" in err) {
    const errs = (err as { errors?: Array<{ extensions?: { code?: string } }> })
      .errors;
    if (Array.isArray(errs)) {
      return errs.some(
        (e) => e?.extensions?.code === "schedule_end_before_start",
      );
    }
  }
  return false;
}

function validateAll(values: {
  playlist_id: string;
  weekdays: boolean[];
  start: string;
  end: string;
  priority: number;
}): Errors {
  const errors: Errors = {};
  if (!values.playlist_id) {
    errors.playlist = "signage.admin.schedules.error.playlist_required";
  }
  if (!values.weekdays.some(Boolean)) {
    errors.weekdays = "signage.admin.schedules.error.weekdays_required";
  }
  const startN = hhmmFromString(values.start);
  const endN = hhmmFromString(values.end);
  if (startN === null || endN === null) {
    errors.time = "signage.admin.schedules.error.time_format";
  } else if (startN === endN) {
    errors.time = "signage.admin.schedules.error.start_equals_end";
  } else if (startN > endN) {
    // D-07: any same-day reversal is a midnight span (no error.start_after_end
    // emitted from client-side validation).
    errors.time = "signage.admin.schedules.error.midnight_span";
  }
  return errors;
}

export function ScheduleEditDialog({
  open,
  onOpenChange,
  schedule,
}: ScheduleEditDialogProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const isEdit = !!schedule;

  const [playlist_id, setPlaylistId] = useState("");
  const [weekdays, setWeekdays] = useState<boolean[]>(INIT_WEEKDAYS);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [priority, setPriority] = useState(0);
  const [enabled, setEnabled] = useState(true);
  const [touched, setTouched] = useState<Touched>({});
  const [errors, setErrors] = useState<Errors>({});

  // Reset / hydrate when dialog opens or target schedule changes.
  useEffect(() => {
    if (!open) return;
    if (schedule) {
      setPlaylistId(schedule.playlist_id);
      setWeekdays(weekdayMaskToArray(schedule.weekday_mask));
      setStart(hhmmToString(schedule.start_hhmm));
      setEnd(hhmmToString(schedule.end_hhmm));
      setPriority(schedule.priority);
      setEnabled(schedule.enabled);
    } else {
      setPlaylistId("");
      setWeekdays(INIT_WEEKDAYS.slice());
      setStart("");
      setEnd("");
      setPriority(0);
      setEnabled(true);
    }
    setTouched({});
    setErrors({});
  }, [open, schedule]);

  const { data: playlists = [] } = useQuery({
    queryKey: signageKeys.playlists(),
    queryFn: signageApi.listPlaylists,
    enabled: open,
  });

  const createMutation = useMutation({
    mutationFn: (body: SignageScheduleCreate) =>
      signageApi.createSchedule(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: signageKeys.schedules() });
      toast.success(t("signage.admin.schedules.toast.created"));
      onOpenChange(false);
    },
    onError: (err) => {
      if (isScheduleEndBeforeStartError(err)) {
        setErrors((prev) => ({
          ...prev,
          time: "signage.admin.schedules.error.start_after_end",
        }));
        setTouched((prev) => ({ ...prev, time: true }));
        return;
      }
      const detail = err instanceof Error ? err.message : String(err);
      toast.error(
        t("signage.admin.schedules.error.save_failed", { detail }),
      );
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: SignageScheduleUpdate }) =>
      signageApi.updateSchedule(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: signageKeys.schedules() });
      toast.success(t("signage.admin.schedules.toast.updated"));
      onOpenChange(false);
    },
    onError: (err) => {
      if (isScheduleEndBeforeStartError(err)) {
        setErrors((prev) => ({
          ...prev,
          time: "signage.admin.schedules.error.start_after_end",
        }));
        setTouched((prev) => ({ ...prev, time: true }));
        return;
      }
      const detail = err instanceof Error ? err.message : String(err);
      toast.error(
        t("signage.admin.schedules.error.save_failed", { detail }),
      );
    },
  });

  const pending = createMutation.isPending || updateMutation.isPending;

  function revalidateField(field: FieldName) {
    const all = validateAll({ playlist_id, weekdays, start, end, priority });
    // Only surface errors for fields the user has touched (plus any that
    // were previously surfaced — keep those visible until fixed).
    setErrors((prev) => {
      const next: Errors = { ...prev };
      if (all[field]) next[field] = all[field];
      else delete next[field];
      // Cross-field revalidation for time pair
      if (field === "time" || field === "playlist" || field === "weekdays") {
        if (all.time && touched.time) next.time = all.time;
        else if (!all.time) delete next.time;
      }
      return next;
    });
  }

  function markTouched(field: FieldName) {
    setTouched((prev) => ({ ...prev, [field]: true }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const all = validateAll({ playlist_id, weekdays, start, end, priority });
    setTouched({ playlist: true, weekdays: true, time: true, priority: true });
    setErrors(all);
    if (Object.keys(all).length > 0) return;

    const startN = hhmmFromString(start)!;
    const endN = hhmmFromString(end)!;
    const body = {
      playlist_id,
      weekday_mask: weekdayMaskFromArray(weekdays),
      start_hhmm: startN,
      end_hhmm: endN,
      priority: Math.max(0, Math.floor(priority)),
      enabled,
    };
    if (isEdit && schedule) {
      updateMutation.mutate({ id: schedule.id, body });
    } else {
      createMutation.mutate(body as SignageScheduleCreate);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>
              {isEdit
                ? t("signage.admin.schedules.page_title")
                : t("signage.admin.schedules.new_cta")}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* Playlist select */}
            <div className="space-y-2">
              <Label htmlFor="sched-playlist">
                {t("signage.admin.schedules.field.playlist.label")}
              </Label>
              <Select
                value={playlist_id}
                onValueChange={(v: string) => {
                  setPlaylistId(v);
                  if (touched.playlist) revalidateField("playlist");
                }}
              >
                <SelectTrigger
                  id="sched-playlist"
                  aria-invalid={errors.playlist ? true : undefined}
                  onBlur={() => {
                    markTouched("playlist");
                    revalidateField("playlist");
                  }}
                >
                  <SelectValue
                    placeholder={t(
                      "signage.admin.schedules.field.playlist.placeholder",
                    )}
                  />
                </SelectTrigger>
                <SelectContent>
                  {playlists.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.playlist && (
                <p className="text-sm text-destructive">{t(errors.playlist)}</p>
              )}
            </div>

            {/* Weekdays */}
            <div className="space-y-2">
              <Label>{t("signage.admin.schedules.field.weekdays.label")}</Label>
              <WeekdayCheckboxRow
                value={weekdays}
                onChange={(next) => {
                  setWeekdays(next);
                  if (touched.weekdays) revalidateField("weekdays");
                }}
                error={!!errors.weekdays}
              />
              <p className="text-sm text-muted-foreground">
                {t("signage.admin.schedules.field.weekdays.help")}
              </p>
              {errors.weekdays && (
                <p className="text-sm text-destructive">{t(errors.weekdays)}</p>
              )}
            </div>

            {/* Start / End time */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="sched-start">
                  {t("signage.admin.schedules.field.start.label")}
                </Label>
                <Input
                  id="sched-start"
                  type="time"
                  value={start}
                  onChange={(e) => {
                    setStart(e.target.value);
                    if (touched.time) revalidateField("time");
                  }}
                  onBlur={() => {
                    markTouched("time");
                    revalidateField("time");
                  }}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sched-end">
                  {t("signage.admin.schedules.field.end.label")}
                </Label>
                <Input
                  id="sched-end"
                  type="time"
                  value={end}
                  onChange={(e) => {
                    setEnd(e.target.value);
                    if (touched.time) revalidateField("time");
                  }}
                  onBlur={() => {
                    markTouched("time");
                    revalidateField("time");
                  }}
                />
              </div>
            </div>
            {errors.time && (
              <p className="text-sm text-destructive">{t(errors.time)}</p>
            )}

            {/* Priority */}
            <div className="space-y-2">
              <Label htmlFor="sched-priority">
                {t("signage.admin.schedules.field.priority.label")}
              </Label>
              <Input
                id="sched-priority"
                type="number"
                min={0}
                step={1}
                value={priority}
                onChange={(e) =>
                  setPriority(parseInt(e.target.value, 10) || 0)
                }
              />
              <p className="text-sm text-muted-foreground">
                {t("signage.admin.schedules.field.priority.help")}
              </p>
            </div>

            {/* Enabled */}
            <label className="flex items-center gap-2 cursor-pointer">
              <Checkbox
                checked={enabled}
                onCheckedChange={(c) => setEnabled(c === true)}
              />
              <span className="text-sm">
                {t("signage.admin.schedules.field.enabled.label")}
              </span>
            </label>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={pending}
            >
              {t("signage.admin.schedules.cancel_cta")}
            </Button>
            <Button type="submit" disabled={pending}>
              {isEdit
                ? t("signage.admin.schedules.save_cta")
                : t("signage.admin.schedules.create_cta")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
