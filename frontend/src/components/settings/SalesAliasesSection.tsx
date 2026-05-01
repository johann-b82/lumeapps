import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/apiClient";
import { salesKeys } from "@/lib/queryKeys";

/**
 * SalesAliasesSection — manual alias CRUD for the sales-rep mapping
 * table. Lives on /settings/hr below the Personio card. Canonical rows
 * (auto-derived from the configured sales departments on every Personio
 * sync) are read-only with a padlock icon. Manual rows can be created
 * (handles nicknames like GUENNI) and deleted from this surface.
 */

interface SalesAliasRow {
  id: number;
  personio_employee_id: number;
  employee_token: string;
  is_canonical: boolean;
}

async function fetchAliases(): Promise<SalesAliasRow[]> {
  return apiClient<SalesAliasRow[]>("/api/admin/sales-aliases");
}

async function createAlias(payload: {
  personio_employee_id: number;
  employee_token: string;
}): Promise<SalesAliasRow> {
  return apiClient<SalesAliasRow>("/api/admin/sales-aliases", {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

async function deleteAlias(id: number): Promise<void> {
  await apiClient<unknown>(`/api/admin/sales-aliases/${id}`, {
    method: "DELETE",
  });
}

export function SalesAliasesSection() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [employeeId, setEmployeeId] = useState("");
  const [token, setToken] = useState("");

  const aliases = useQuery({
    queryKey: salesKeys.aliases(),
    queryFn: fetchAliases,
  });

  const createMut = useMutation({
    mutationFn: createAlias,
    onSuccess: () => {
      toast.success(t("settings.sales_aliases.created"));
      setEmployeeId("");
      setToken("");
      qc.invalidateQueries({ queryKey: salesKeys.aliases() });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const deleteMut = useMutation({
    mutationFn: deleteAlias,
    onSuccess: () => {
      toast.success(t("settings.sales_aliases.deleted"));
      qc.invalidateQueries({ queryKey: salesKeys.aliases() });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const empId = parseInt(employeeId, 10);
    if (Number.isNaN(empId) || !token.trim()) {
      toast.error(t("settings.sales_aliases.invalid_input"));
      return;
    }
    createMut.mutate({
      personio_employee_id: empId,
      employee_token: token.trim().toUpperCase(),
    });
  };

  return (
    <Card id="sales-aliases">
      <CardHeader>
        <CardTitle>{t("settings.sales_aliases.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <p className="text-sm text-muted-foreground">
          {t("settings.sales_aliases.description")}
        </p>

        {/* Existing aliases table */}
        <div>
          {aliases.isLoading && (
            <p className="text-sm text-muted-foreground">
              {t("settings.sales_aliases.loading")}
            </p>
          )}
          {aliases.isError && (
            <p className="text-sm text-destructive">
              {t("settings.sales_aliases.load_error")}
            </p>
          )}
          {aliases.data && aliases.data.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {t("settings.sales_aliases.empty")}
            </p>
          )}
          {aliases.data && aliases.data.length > 0 && (
            <table className="w-full text-sm">
              <thead className="text-left">
                <tr className="border-b border-border">
                  <th className="py-2 font-medium">
                    {t("settings.sales_aliases.col_token")}
                  </th>
                  <th className="py-2 font-medium">
                    {t("settings.sales_aliases.col_employee_id")}
                  </th>
                  <th className="py-2 font-medium">
                    {t("settings.sales_aliases.col_kind")}
                  </th>
                  <th className="py-2 font-medium text-right">
                    {t("settings.sales_aliases.col_actions")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {aliases.data.map((a) => (
                  <tr key={a.id} className="border-b border-border/50">
                    <td className="py-2 font-mono">{a.employee_token}</td>
                    <td className="py-2">{a.personio_employee_id}</td>
                    <td className="py-2 text-muted-foreground">
                      {a.is_canonical
                        ? t("settings.sales_aliases.canonical")
                        : t("settings.sales_aliases.manual")}
                    </td>
                    <td className="py-2 text-right">
                      {a.is_canonical ? (
                        <Lock
                          className="inline h-4 w-4 text-muted-foreground"
                          aria-label={t("settings.sales_aliases.canonical_lock")}
                        />
                      ) : (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteMut.mutate(a.id)}
                          disabled={deleteMut.isPending}
                          aria-label={t("settings.sales_aliases.delete")}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Add manual alias form */}
        <form
          onSubmit={onSubmit}
          className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end pt-2 border-t border-border"
        >
          <div className="space-y-1.5">
            <Label htmlFor="alias-employee-id">
              {t("settings.sales_aliases.form_employee_id")}
            </Label>
            <Input
              id="alias-employee-id"
              type="number"
              value={employeeId}
              onChange={(e) => setEmployeeId(e.target.value)}
              placeholder="123456"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="alias-token">
              {t("settings.sales_aliases.form_token")}
            </Label>
            <Input
              id="alias-token"
              type="text"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="GUENNI"
              className="font-mono"
            />
          </div>
          <Button type="submit" disabled={createMut.isPending}>
            {t("settings.sales_aliases.add")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
