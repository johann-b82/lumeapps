import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Search, ArrowUp, ArrowDown, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { fetchSalesRecords, type SalesRecordRow } from "@/lib/api";
import { useTableState } from "@/hooks/useTableState";

const PAGE_SIZE = 50;

// Phase 61: useTableState requires T extends Record<string, unknown> but
// SalesRecordRow has concrete fields only. Intersect at the call site so
// concrete field types survive (customer_name: string | null, etc.)
// while the generic constraint is satisfied. No change to
// SalesRecordRow, no change to useTableState (D-02).
type SalesRow = SalesRecordRow & Record<string, unknown>;

interface SalesTableProps {
  startDate?: string;
  endDate?: string;
}

export function SalesTable({ startDate, endDate }: SalesTableProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["sales-records", startDate, endDate, search],
    queryFn: () =>
      fetchSalesRecords({
        start_date: startDate,
        end_date: endDate,
        search: search || undefined,
      }),
  });

  const { processed, sortKey, sortDir, toggleSort } = useTableState<SalesRow>(
    data as SalesRow[] | undefined,
    { key: "order_date", dir: "desc" },
  );

  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(processed.length / PAGE_SIZE));
  // Reset to first page whenever the underlying result set or sort changes.
  useEffect(() => {
    setPage(1);
  }, [search, sortKey, sortDir, data?.length]);
  const safePage = Math.min(page, totalPages);
  const pageRows = processed.slice(
    (safePage - 1) * PAGE_SIZE,
    safePage * PAGE_SIZE,
  );

  const formatCurrency = (v: number | null) =>
    v == null
      ? "—"
      : new Intl.NumberFormat(locale, {
          style: "currency",
          currency: "EUR",
          maximumFractionDigits: 0,
        }).format(v);

  const formatDate = (d: string | null) => {
    if (!d) return "—";
    return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(
      new Date(d)
    );
  };

  const columns = [
    { key: "order_number", label: t("dashboard.table.order"), align: "left" as const },
    { key: "customer_name", label: t("dashboard.table.customer"), align: "left" as const },
    { key: "project_name", label: t("dashboard.table.project"), align: "left" as const },
    { key: "order_date", label: t("dashboard.table.date"), align: "left" as const },
    { key: "total_value", label: t("dashboard.table.total"), align: "right" as const },
    { key: "remaining_value", label: t("dashboard.table.remaining"), align: "right" as const },
  ];

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <p className="text-xl font-semibold">{t("dashboard.table.title")}</p>
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t("dashboard.table.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              {columns.map((col) => (
                <th key={col.key} className={`px-3 py-0 font-medium text-${col.align}`}>
                  <button
                    onClick={() => toggleSort(col.key)}
                    className="flex items-center gap-1 py-2 hover:text-foreground transition-colors w-full"
                    style={{ justifyContent: col.align === "right" ? "flex-end" : "flex-start" }}
                  >
                    {col.label}
                    {sortKey === col.key && (
                      sortDir === "asc"
                        ? <ArrowUp className="h-3 w-3" />
                        : <ArrowDown className="h-3 w-3" />
                    )}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-3 py-8 text-center text-muted-foreground">
                  {t("dashboard.table.loading")}
                </td>
              </tr>
            ) : !processed.length ? (
              <tr>
                <td colSpan={6} className="px-3 py-8 text-center text-muted-foreground">
                  {t("dashboard.table.empty")}
                </td>
              </tr>
            ) : (
              pageRows.map((row) => (
                <tr key={row.id} className="border-b border-border last:border-0 hover:bg-muted/30">
                  <td className="px-3 py-2 font-mono text-xs">{row.order_number}</td>
                  <td className="px-3 py-2">{row.customer_name ?? "—"}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.project_name ?? "—"}</td>
                  <td className="px-3 py-2">{formatDate(row.order_date)}</td>
                  <td className="px-3 py-2 text-right">{formatCurrency(row.total_value)}</td>
                  <td className="px-3 py-2 text-right">{formatCurrency(row.remaining_value)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {data && (
        <div className="flex items-center justify-between mt-3">
          <p className="text-xs text-muted-foreground">
            {processed.length === 0
              ? `0 ${t("dashboard.table.records")}`
              : `${(safePage - 1) * PAGE_SIZE + 1}–${Math.min(
                  safePage * PAGE_SIZE,
                  processed.length,
                )} / ${processed.length} ${t("dashboard.table.records")}`}
          </p>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage === 1}
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-xs text-muted-foreground tabular-nums">
                {safePage} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage === totalPages}
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
