import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import {
  maintenanceApi,
  type MachineInput,
  type MachineStatus,
} from "@/lib/maintenanceApi";

const EMPTY: MachineInput = {
  name: "",
  inventory_no: "",
  location: "",
  manufacturer: "",
  model: "",
  responsible: "",
  status: "active",
  notes: "",
};

export function MaintenanceMachinesPage() {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();
  const qc = useQueryClient();

  const { data: machines, isLoading } = useQuery({
    queryKey: ["maintenance", "machines"],
    queryFn: maintenanceApi.listMachines,
  });

  const [showForm, setShowForm] = useState(false);
  const [draft, setDraft] = useState<MachineInput>(EMPTY);

  const create = useMutation({
    mutationFn: () => maintenanceApi.createMachine(draft),
    onSuccess: () => {
      toast.success(t("maintenance.machines.created"));
      setDraft(EMPTY);
      setShowForm(false);
      qc.invalidateQueries({ queryKey: ["maintenance", "machines"] });
    },
    onError: (e: unknown) => toast.error(String(e)),
  });

  const remove = useMutation({
    mutationFn: (id: string) => maintenanceApi.deleteMachine(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["maintenance", "machines"] });
    },
    onError: (e: unknown) => toast.error(String(e)),
  });

  type StrField =
    | "name"
    | "inventory_no"
    | "location"
    | "manufacturer"
    | "model"
    | "responsible";
  const field = (key: StrField, label: string) => (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <input
        className="border rounded px-2 py-1.5"
        value={draft[key] ?? ""}
        onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
      />
    </label>
  );

  return (
    <div className="max-w-6xl mx-auto px-6 py-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">{t("maintenance.machines.heading")}</h1>
        <button
          className="inline-flex items-center gap-1.5 rounded-md bg-primary text-primary-foreground px-3 py-1.5 text-sm hover:opacity-90"
          onClick={() => setShowForm((v) => !v)}
        >
          <Plus className="h-4 w-4" />
          {t("maintenance.machines.new")}
        </button>
      </div>

      {showForm && (
        <div className="border rounded-lg p-4 mb-6 bg-card">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {field("name", t("maintenance.machines.col.name"))}
            {field("inventory_no", t("maintenance.machines.col.inventory_no"))}
            {field("location", t("maintenance.machines.col.location"))}
            {field("manufacturer", t("maintenance.machines.col.manufacturer"))}
            {field("model", t("maintenance.machines.col.model"))}
            {field("responsible", t("maintenance.machines.col.responsible"))}
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">
                {t("maintenance.machines.col.status")}
              </span>
              <select
                className="border rounded px-2 py-1.5 bg-background"
                value={draft.status}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, status: e.target.value as MachineStatus }))
                }
              >
                <option value="active">{t("maintenance.status.active")}</option>
                <option value="inactive">{t("maintenance.status.inactive")}</option>
              </select>
            </label>
          </div>
          <div className="mt-4 flex gap-2">
            <button
              className="rounded-md bg-primary text-primary-foreground px-3 py-1.5 text-sm hover:opacity-90 disabled:opacity-50"
              disabled={!draft.name.trim() || create.isPending}
              onClick={() => create.mutate()}
            >
              {t("maintenance.machines.save")}
            </button>
            <button
              className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent/10"
              onClick={() => {
                setShowForm(false);
                setDraft(EMPTY);
              }}
            >
              {t("common.cancel")}
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-muted-foreground">…</p>
      ) : !machines || machines.length === 0 ? (
        <p className="text-muted-foreground">{t("maintenance.machines.empty")}</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left border-b">
              <th className="py-2">{t("maintenance.machines.col.name")}</th>
              <th>{t("maintenance.machines.col.inventory_no")}</th>
              <th>{t("maintenance.machines.col.location")}</th>
              <th>{t("maintenance.machines.col.responsible")}</th>
              <th>{t("maintenance.machines.col.status")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {machines.map((m) => (
              <tr key={m.id} className="border-b hover:bg-accent/5">
                <td className="py-2">
                  <button
                    className="text-blue-600 hover:underline font-medium"
                    onClick={() => setLocation(`/production/maintenance/${m.id}`)}
                  >
                    {m.name}
                  </button>
                </td>
                <td className="font-mono text-xs">{m.inventory_no ?? "—"}</td>
                <td>{m.location ?? "—"}</td>
                <td>{m.responsible ?? "—"}</td>
                <td>
                  <span
                    className={
                      m.status === "active"
                        ? "text-emerald-600"
                        : "text-muted-foreground"
                    }
                  >
                    {t(`maintenance.status.${m.status}`)}
                  </span>
                </td>
                <td className="whitespace-nowrap text-right">
                  <button
                    className="text-blue-600 mr-3"
                    onClick={() => setLocation(`/production/maintenance/${m.id}`)}
                  >
                    {t("maintenance.machines.open")}
                  </button>
                  <button
                    className="text-red-600"
                    onClick={() => {
                      if (confirm(t("maintenance.machines.confirmDelete")))
                        remove.mutate(m.id);
                    }}
                  >
                    {t("common.delete")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
