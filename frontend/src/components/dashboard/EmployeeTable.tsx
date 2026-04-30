import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Search, ArrowUp, ArrowDown } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { SegmentedControl } from "@/components/ui/segmented-control";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useEmployeesWithOvertime } from "@/lib/api";
import { useSettings } from "@/hooks/useSettings";
import { useTableState } from "@/hooks/useTableState";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";

export function EmployeeTable() {
  const { t, i18n } = useTranslation();
  const { data: settings } = useSettings();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"overtime" | "active" | "all">("overtime");

  // Phase 60: attendance aggregates (total_hours / overtime_hours / overtime_ratio)
  // reflect the active DateRangeContext window. Roster presence is NOT filtered
  // by attendance (D-12) — only the aggregate columns change with the range.
  const { range } = useDateRange();
  const date_from = toApiDate(range.from);
  const date_to = toApiDate(range.to);

  const { data, isLoading } = useEmployeesWithOvertime({
    search: search || undefined,
    date_from,
    date_to,
  });

  const rows = useMemo(
    () =>
      data?.map((r) => ({
        ...r,
        name: [r.first_name, r.last_name].filter(Boolean).join(" ") || "—",
      })),
    [data]
  );

  const selectedDepts = settings?.personio_production_dept ?? [];

  const filtered = useMemo(
    () => {
      if (!rows) return rows;
      let result = rows;
      // Filter by selected departments from Settings
      if (selectedDepts.length > 0) {
        result = result.filter((r) => r.department != null && selectedDepts.includes(r.department));
      }
      if (filter === "overtime") return result.filter((r) => r.overtime_hours > 0);
      if (filter === "active") return result.filter((r) => r.status === "active");
      return result;
    },
    [rows, filter, selectedDepts]
  );

  const { processed, sortKey, sortDir, toggleSort } =
    useTableState(filtered, { key: "overtime_hours", dir: "desc" });

  const columns = [
    { key: "name", label: t("hr.table.name"), align: "left" as const },
    { key: "department", label: t("hr.table.department"), align: "left" as const },
    { key: "position", label: t("hr.table.position"), align: "left" as const },
    { key: "status", label: t("hr.table.status"), align: "left" as const },
    { key: "weekly_working_hours", label: t("hr.table.hours"), align: "right" as const },
    { key: "total_hours", label: t("hr.table.totalHours"), align: "right" as const },
    { key: "overtime_hours", label: t("hr.table.overtime"), align: "right" as const },
    { key: "overtime_ratio", label: t("hr.table.overtimeRatio"), align: "right" as const },
  ];

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <p className="text-xl font-semibold">{t("hr.table.title")}</p>
          {(() => {
            const segments = [
              { value: "overtime" as const, label: t("hr.table.showOvertime") },
              { value: "active" as const, label: t("hr.table.showActive") },
              { value: "all" as const, label: t("hr.table.showAll") },
            ];
            return (
              <>
                <div data-testid="employee-filter-desktop" className="hidden md:block">
                  <SegmentedControl<"overtime" | "active" | "all">
                    segments={segments}
                    value={filter}
                    onChange={setFilter}
                  />
                </div>
                <div data-testid="employee-filter-mobile" className="md:hidden">
                  <Select<"overtime" | "active" | "all">
                    value={filter}
                    onValueChange={setFilter}
                  >
                    <SelectTrigger className="w-36">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {segments.map((s) => (
                        <SelectItem key={s.value} value={s.value}>
                          {s.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            );
          })()}
        </div>
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t("hr.table.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              {columns.map((col) => (
                <th key={col.key} className={`px-3 py-0 font-medium text-${col.align}`}>
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={() => toggleSort(col.key)}
                    className="w-full py-2 h-auto font-medium"
                    style={{ justifyContent: col.align === "right" ? "flex-end" : "flex-start" }}
                  >
                    {col.label}
                    {sortKey === col.key && (
                      sortDir === "asc"
                        ? <ArrowUp className="h-3 w-3" />
                        : <ArrowDown className="h-3 w-3" />
                    )}
                  </Button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-muted-foreground">
                  {t("hr.table.loading")}
                </td>
              </tr>
            ) : !processed.length ? (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-muted-foreground">
                  {t("hr.table.empty")}
                </td>
              </tr>
            ) : (
              processed.map((row) => (
                <tr key={row.id} className="border-b border-border last:border-0 hover:bg-muted/30">
                  <td className="px-3 py-2 font-medium">{row.name}</td>
                  <td className="px-3 py-2">{row.department ?? "—"}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.position ?? "—"}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                        row.status === "active"
                          ? "bg-[var(--color-success)]/20 text-foreground"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {row.status ?? "—"}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    {row.weekly_working_hours != null ? `${row.weekly_working_hours}h` : "—"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {row.total_hours > 0 ? `${row.total_hours}h` : "—"}
                  </td>
                  <td className={`px-3 py-2 text-right font-medium ${row.overtime_hours > 0 ? "text-destructive" : ""}`}>
                    {row.overtime_hours > 0 ? `${row.overtime_hours}h` : "—"}
                  </td>
                  <td className={`px-3 py-2 text-right font-medium ${row.overtime_ratio != null ? "text-destructive" : ""}`}>
                    {row.overtime_ratio != null
                      ? new Intl.NumberFormat(locale, { style: "percent", minimumFractionDigits: 1 }).format(row.overtime_ratio)
                      : "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {rows && (
        <p className="text-xs text-muted-foreground mt-2">
          {processed.length} {t("hr.table.records")}
        </p>
      )}
    </Card>
  );
}
