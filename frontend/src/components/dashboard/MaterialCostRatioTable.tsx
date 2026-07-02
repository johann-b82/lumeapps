/**
 * MaterialCostRatioTable — verification table for the Materialkostenquote.
 *
 * One row per consumed article in the window (window on buch_datum): net
 * consumed qty, the unit price used (newest WE price), and the resulting
 * material cost. Mirrors OtdTable (sortable columns, search, pagination).
 * Articles with no WE purchase price show "—" for price/cost and are tinted
 * muted — they are excluded from the Materialkosten total.
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
import { fetchMaterialCostRatioList, type MaterialCostRatioRow } from "@/lib/api";
import { financeKeys } from "@/lib/queryKeys";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";
import { useTableState } from "@/hooks/useTableState";

const PAGE_SIZE = 50;

type Row = MaterialCostRatioRow & Record<string, unknown>;

export function MaterialCostRatioTable() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const [search, setSearch] = useState("");

  const { range } = useDateRange();
  const date_from = toApiDate(range.from);
  const date_to = toApiDate(range.to);

  const { data, isLoading } = useQuery({
    queryKey: financeKeys.materialCostRatioList(date_from, date_to),
    queryFn: () => fetchMaterialCostRatioList({ date_from, date_to }),
  });

  const filtered: Row[] | undefined = data
    ?.filter((row) => {
      if (!search.trim()) return true;
      const needle = search.toLowerCase();
      return [row.artikelnr, row.article_name]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle));
    })
    .map((r) => r as Row);

  const { processed, sortKey, sortDir, toggleSort } = useTableState<Row>(
    filtered,
    { key: "material_cost", dir: "desc" },
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

  const formatQty = (n: number) =>
    new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(n);

  const formatEur = (n: number | null) =>
    n == null
      ? "—"
      : new Intl.NumberFormat(locale, {
          style: "currency",
          currency: "EUR",
          maximumFractionDigits: 2,
        }).format(n);

  const columns = [
    { key: "artikelnr",     label: t("finance.table.article"),      align: "left" as const },
    { key: "article_name",  label: t("finance.table.articleName"),  align: "left" as const },
    { key: "consumed_qty",  label: t("finance.table.consumed"),     align: "right" as const },
    { key: "unit_price",    label: t("finance.table.unitPrice"),    align: "right" as const },
    { key: "material_cost", label: t("finance.table.materialCost"), align: "right" as const },
  ];

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <p className="text-xl font-semibold">{t("finance.table.title")}</p>
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
        <table className="w-full min-w-[720px] text-sm">
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
                  key={row.artikelnr}
                  className={`border-b border-border last:border-0 hover:bg-muted/30 ${
                    row.has_price ? "" : "text-muted-foreground"
                  }`}
                >
                  <td className="px-3 py-2 font-mono text-xs">{row.artikelnr}</td>
                  <td className="px-3 py-2 max-w-xs truncate">
                    {row.article_name ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatQty(row.consumed_qty)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatEur(row.unit_price)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatEur(row.material_cost)}
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
