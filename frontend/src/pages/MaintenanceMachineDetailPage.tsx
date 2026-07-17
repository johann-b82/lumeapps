import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useRoute } from "wouter";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Download, Trash2, Upload } from "lucide-react";
import {
  downloadMachineSheet,
  maintenanceApi,
  openMaintenanceFile,
  type FileKind,
  type IntervalType,
  type MachineDetail,
  type TaskInput,
} from "@/lib/maintenanceApi";

const INTERVALS: IntervalType[] = [
  "daily",
  "weekly",
  "monthly",
  "quarterly",
  "interval_weeks",
];

function machineKey(id: string) {
  return ["maintenance", "machine", id] as const;
}

export function MaintenanceMachineDetailPage() {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();
  const [, params] = useRoute("/production/maintenance/:id");
  const id = params?.id ?? "";

  const { data: machine, isLoading } = useQuery({
    queryKey: machineKey(id),
    queryFn: () => maintenanceApi.getMachine(id),
    enabled: !!id,
  });

  if (isLoading) return <p className="max-w-5xl mx-auto px-6 py-6">…</p>;
  if (!machine)
    return (
      <p className="max-w-5xl mx-auto px-6 py-6 text-muted-foreground">
        {t("maintenance.detail.notFound")}
      </p>
    );

  return (
    <div className="max-w-5xl mx-auto px-6 py-6">
      <button
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-3"
        onClick={() => setLocation("/production/maintenance")}
      >
        <ArrowLeft className="h-4 w-4" />
        {t("maintenance.detail.back")}
      </button>

      <h1 className="text-xl font-semibold">{machine.name}</h1>
      <p className="text-sm text-muted-foreground mb-6">
        {[machine.inventory_no, machine.location, machine.responsible]
          .filter(Boolean)
          .join(" · ") || "—"}
      </p>

      <TasksSection machine={machine} qcKey={machineKey(id)} />
      <SheetSection machineId={id} machineName={machine.name} />
      <FilesSection machine={machine} qcKey={machineKey(id)} />
    </div>
  );
}

// ── Tasks ─────────────────────────────────────────────────────────────────

function TasksSection({
  machine,
  qcKey,
}: {
  machine: MachineDetail;
  qcKey: readonly unknown[];
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: qcKey });

  const intervalLabel = (interval: IntervalType, weeks: number | null): string =>
    interval === "interval_weeks"
      ? t("maintenance.interval.every_n_weeks", { n: weeks ?? "?" })
      : t(`maintenance.interval.${interval}`);

  const [draft, setDraft] = useState<TaskInput>({
    title: "",
    instructions: "",
    interval_type: "weekly",
    interval_weeks: null,
  });

  const create = useMutation({
    mutationFn: () =>
      maintenanceApi.createTask(machine.id, {
        ...draft,
        interval_weeks:
          draft.interval_type === "interval_weeks"
            ? draft.interval_weeks || 1
            : null,
      }),
    onSuccess: () => {
      toast.success(t("maintenance.tasks.added"));
      setDraft({
        title: "",
        instructions: "",
        interval_type: "weekly",
        interval_weeks: null,
      });
      invalidate();
    },
    onError: (e: unknown) => toast.error(String(e)),
  });

  const remove = useMutation({
    mutationFn: (taskId: string) => maintenanceApi.deleteTask(taskId),
    onSuccess: invalidate,
    onError: (e: unknown) => toast.error(String(e)),
  });

  return (
    <section className="mb-8">
      <h2 className="text-lg font-medium mb-3">{t("maintenance.tasks.heading")}</h2>

      {machine.tasks.length === 0 ? (
        <p className="text-muted-foreground text-sm mb-4">
          {t("maintenance.tasks.empty")}
        </p>
      ) : (
        <table className="w-full text-sm mb-4">
          <thead>
            <tr className="text-left border-b">
              <th className="py-2">{t("maintenance.tasks.col.title")}</th>
              <th>{t("maintenance.tasks.col.interval")}</th>
              <th>{t("maintenance.tasks.col.instructions")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {machine.tasks.map((task) => (
              <tr key={task.id} className="border-b">
                <td className="py-2 font-medium">{task.title}</td>
                <td className="whitespace-nowrap">
                  {intervalLabel(task.interval_type, task.interval_weeks)}
                </td>
                <td className="text-muted-foreground">{task.instructions || "—"}</td>
                <td className="text-right">
                  <button
                    className="text-red-600"
                    aria-label={t("common.delete")}
                    onClick={() => remove.mutate(task.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="border rounded-lg p-4 bg-card grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">
            {t("maintenance.tasks.col.title")}
          </span>
          <input
            className="border rounded px-2 py-1.5"
            value={draft.title}
            onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
          />
        </label>
        <div className="flex gap-2">
          <label className="flex flex-col gap-1 text-sm flex-1">
            <span className="text-muted-foreground">
              {t("maintenance.tasks.col.interval")}
            </span>
            <select
              className="border rounded px-2 py-1.5 bg-background"
              value={draft.interval_type}
              onChange={(e) =>
                setDraft((d) => ({
                  ...d,
                  interval_type: e.target.value as IntervalType,
                }))
              }
            >
              {INTERVALS.map((iv) => (
                <option key={iv} value={iv}>
                  {iv === "interval_weeks"
                    ? t("maintenance.interval.interval_weeks_option")
                    : t(`maintenance.interval.${iv}`)}
                </option>
              ))}
            </select>
          </label>
          {draft.interval_type === "interval_weeks" && (
            <label className="flex flex-col gap-1 text-sm w-24">
              <span className="text-muted-foreground">
                {t("maintenance.interval.weeks")}
              </span>
              <input
                type="number"
                min={1}
                className="border rounded px-2 py-1.5"
                value={draft.interval_weeks ?? ""}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...d,
                    interval_weeks: e.target.value ? Number(e.target.value) : null,
                  }))
                }
              />
            </label>
          )}
        </div>
        <label className="flex flex-col gap-1 text-sm sm:col-span-2">
          <span className="text-muted-foreground">
            {t("maintenance.tasks.col.instructions")}
          </span>
          <textarea
            className="border rounded px-2 py-1.5"
            rows={2}
            value={draft.instructions}
            onChange={(e) =>
              setDraft((d) => ({ ...d, instructions: e.target.value }))
            }
          />
        </label>
        <div className="sm:col-span-2">
          <button
            className="rounded-md bg-primary text-primary-foreground px-3 py-1.5 text-sm hover:opacity-90 disabled:opacity-50"
            disabled={!draft.title.trim() || create.isPending}
            onClick={() => create.mutate()}
          >
            {t("maintenance.tasks.add")}
          </button>
        </div>
      </div>
    </section>
  );
}

// ── Printable sheet ─────────────────────────────────────────────────────────

function SheetSection({
  machineId,
  machineName,
}: {
  machineId: string;
  machineName: string;
}) {
  const { t } = useTranslation();
  const [half, setHalf] = useState<1 | 2>(1);
  const [busy, setBusy] = useState(false);

  const download = async () => {
    setBusy(true);
    try {
      await downloadMachineSheet(machineId, machineName, { half });
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="mb-8">
      <h2 className="text-lg font-medium mb-3">{t("maintenance.sheet.heading")}</h2>
      <div className="flex items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">{t("maintenance.sheet.period")}</span>
          <select
            className="border rounded px-2 py-1.5 bg-background"
            value={half}
            onChange={(e) => setHalf(Number(e.target.value) as 1 | 2)}
          >
            <option value={1}>{t("maintenance.sheet.h1")}</option>
            <option value={2}>{t("maintenance.sheet.h2")}</option>
          </select>
        </label>
        <button
          className="inline-flex items-center gap-1.5 rounded-md bg-primary text-primary-foreground px-3 py-1.5 text-sm hover:opacity-90 disabled:opacity-50"
          disabled={busy}
          onClick={download}
        >
          <Download className="h-4 w-4" />
          {busy ? t("maintenance.sheet.generating") : t("maintenance.sheet.download")}
        </button>
      </div>
      <p className="text-xs text-muted-foreground mt-2">
        {t("maintenance.sheet.hint")}
      </p>
    </section>
  );
}

// ── Files ────────────────────────────────────────────────────────────────────

function FilesSection({
  machine,
  qcKey,
}: {
  machine: MachineDetail;
  qcKey: readonly unknown[];
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: qcKey });
  const inputRef = useRef<HTMLInputElement>(null);
  const [kind, setKind] = useState<FileKind>("plan");

  const upload = useMutation({
    mutationFn: (file: File) => maintenanceApi.uploadFile(machine.id, file, kind),
    onSuccess: () => {
      toast.success(t("maintenance.files.uploaded"));
      invalidate();
      if (inputRef.current) inputRef.current.value = "";
    },
    onError: (e: unknown) => toast.error(String(e)),
  });

  const remove = useMutation({
    mutationFn: (fileId: string) => maintenanceApi.deleteFile(fileId),
    onSuccess: invalidate,
    onError: (e: unknown) => toast.error(String(e)),
  });

  return (
    <section>
      <h2 className="text-lg font-medium mb-3">{t("maintenance.files.heading")}</h2>

      {machine.files.length === 0 ? (
        <p className="text-muted-foreground text-sm mb-4">
          {t("maintenance.files.empty")}
        </p>
      ) : (
        <ul className="mb-4 divide-y border rounded-lg">
          {machine.files.map((f) => (
            <li key={f.id} className="flex items-center justify-between px-3 py-2">
              <div className="min-w-0">
                <button
                  className="text-blue-600 hover:underline truncate"
                  onClick={() => openMaintenanceFile(f.id).catch((e) => toast.error(String(e)))}
                >
                  {f.filename}
                </button>
                <span className="ml-2 text-xs text-muted-foreground">
                  {t(`maintenance.files.kind.${f.file_kind}`)}
                </span>
              </div>
              <button
                className="text-red-600"
                aria-label={t("common.delete")}
                onClick={() => remove.mutate(f.id)}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">{t("maintenance.files.kindLabel")}</span>
          <select
            className="border rounded px-2 py-1.5 bg-background"
            value={kind}
            onChange={(e) => setKind(e.target.value as FileKind)}
          >
            <option value="plan">{t("maintenance.files.kind.plan")}</option>
            <option value="archive">{t("maintenance.files.kind.archive")}</option>
          </select>
        </label>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept=".pdf,.png,.jpg,.jpeg,.xlsx,.xls,.docx,.doc"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) upload.mutate(file);
          }}
        />
        <button
          className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-accent/10 disabled:opacity-50"
          disabled={upload.isPending}
          onClick={() => inputRef.current?.click()}
        >
          <Upload className="h-4 w-4" />
          {upload.isPending ? t("maintenance.files.uploading") : t("maintenance.files.upload")}
        </button>
      </div>
    </section>
  );
}
