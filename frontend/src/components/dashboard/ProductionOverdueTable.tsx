/**
 * ProductionOverdueTable — open & overdue orders (no Lieferschein yet, Zieltermin
 * already past). The acute action list, shown next to "Aufträge in Verzug".
 * Mirrors ProductionVerzugTable at order granularity.
 */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Search,
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { fetchProductionOverdueList, type ProductionOverdueRow } from "@/lib/api";
import { productionKeys } from "@/lib/queryKeys";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";
import { useTableState } from "@/hooks/useTableState";

const PAGE_SIZE = 50;

type Row = ProductionOverdueRow & Record<string, unknown>;

export function ProductionOverdueTable() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const [search, setSearch] = useState("");

  const { range } = useDateRange();
  const date_from = toApiDate(range.from);
  const date_to = toApiDate(range.to);

  const { data, isLoading } = useQuery({
    queryKey: productionKeys.verzugOverdue(date_from, date_to),
    queryFn: () => fetchProductionOverdueList({ date_from, date_to }),
  });

  const filtered: Row[] | undefined = data
    ?.filter((row) => {
      if (!search.trim()) return true;
      const needle = search.toLowerCase();
      return [row.vorgang_nr, row.customer_name, row.adr_nr]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle));
    })
    .map((r) => r as Row);

  const { processed, sortKey, sortDir, toggleSort } = useTableState<Row>(
    filtered,
    { key: "days_overdue", dir: "desc" },
  );

  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(processed.length / PAGE_SIZE));
  useEffect(() => {
    setPage(1);
  }, [search, sortKey, sortDir, data?.length]);
  const safePage = Math.min(page, totalPages);
  const pageRows = processed.slice(
    (safePage - 1) * PAGE_SIZE,
    safePage * PAGE_SIZE,
  );

  const formatDate = (d: string | null) => {
    if (!d) return "—";
    return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(
      new Date(d),
    );
  };

  const columns = [
    { key: "vorgang_nr",    label: t("production.table.auftrag"),  align: "left" as const },
    { key: "customer_name", label: t("production.table.customer"), align: "left" as const },
    { key: "target_date",   label: t("production.table.target"),   align: "left" as const },
    { key: "days_overdue",  label: t("production.overdue.days"),   align: "right" as const },
  ];

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <p className="text-xl font-semibold">{t("production.overdue.title")}</p>
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t("quality.table.search")}
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
                <th
                  key={col.key}
                  className={`px-3 py-0 font-medium text-${col.align}`}
                >
                  <button
                    onClick={() => toggleSort(col.key)}
                    className="flex items-center gap-1 py-2 hover:text-foreground transition-colors w-full"
                    style={{
                      justifyContent:
                        col.align === "right" ? "flex-end" : "flex-start",
                    }}
                  >
                    {col.label}
                    {sortKey === col.key &&
                      (sortDir === "asc" ? (
                        <ArrowUp className="h-3 w-3" />
                      ) : (
                        <ArrowDown className="h-3 w-3" />
                      ))}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-8 text-center text-muted-foreground">
                  {t("quality.table.loading")}
                </td>
              </tr>
            ) : !processed.length ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-8 text-center text-muted-foreground">
                  {t("quality.table.empty")}
                </td>
              </tr>
            ) : (
              pageRows.map((row) => (
                <tr
                  key={row.vorgang_nr}
                  className="border-b border-border last:border-0 hover:bg-muted/30"
                >
                  <td className="px-3 py-2 font-mono text-xs">{row.vorgang_nr}</td>
                  <td className="px-3 py-2">
                    {row.customer_name ?? "—"}
                    {row.adr_nr && (
                      <span className="text-xs text-muted-foreground ml-1">
                        ({row.adr_nr})
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">{formatDate(row.target_date)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-destructive">
                    {row.days_overdue == null
                      ? "—"
                      : new Intl.NumberFormat(locale, {
                          signDisplay: "exceptZero",
                        }).format(row.days_overdue)}
                  </td>
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
              ? `0 ${t("quality.table.records")}`
              : `${(safePage - 1) * PAGE_SIZE + 1}–${Math.min(
                  safePage * PAGE_SIZE,
                  processed.length,
                )} / ${processed.length} ${t("quality.table.records")}`}
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
