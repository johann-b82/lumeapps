import { type ReactNode, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Search, ArrowUp, ArrowDown, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useTableState } from "@/hooks/useTableState";

/**
 * Shared styled data table, extracted from the dashboard SalesTable pattern so
 * every list looks the same: Card + title/search header, bordered scroll box,
 * `bg-muted/50` sortable headers, hover rows, right-aligned numerics, "—" for
 * empty cells, and a Chevron prev/next pager.
 *
 * Sorting is client-side over the rows you pass (opt in via `initialSort` or
 * `sortable`). Pagination is client-side (opt in via `pageSize`). Search is
 * *controlled by the caller* — the input is rendered, but filtering the rows
 * (client- or server-side) stays with the parent so this component makes no
 * assumption about where the data comes from.
 */
export interface DataTableColumn<T> {
  key: string;
  header: ReactNode;
  align?: "left" | "right";
  /** Defaults to the table's sort mode; set false to pin a column unsortable. */
  sortable?: boolean;
  /** Extra <td> classes (the base `px-3 py-2` + alignment is always applied). */
  className?: string;
  /** Custom cell renderer. Defaults to the raw value, or "—" when null/empty. */
  cell?: (row: T) => ReactNode;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[] | undefined;
  rowKey: (row: T) => string | number;
  isLoading?: boolean;
  loadingText?: ReactNode;
  emptyText?: ReactNode;
  title?: ReactNode;
  /** Extra header controls (buttons, selects) rendered left of the search box. */
  actions?: ReactNode;
  search?: { value: string; onChange: (v: string) => void; placeholder?: string };
  initialSort?: { key: string; dir: "asc" | "desc" };
  /** Enable sortable headers. Defaults to true when `initialSort` is given. */
  sortable?: boolean;
  /** Enable client-side pagination at this page size. */
  pageSize?: number;
  minWidth?: number;
  /** Wrap in a Card. Defaults to true when a header (title/search/actions) exists. */
  card?: boolean;
  rowClassName?: (row: T) => string;
  onRowClick?: (row: T) => void;
  rowTestId?: (row: T) => string | undefined;
}

function defaultCell(value: unknown): ReactNode {
  return value == null || value === "" ? "—" : String(value);
}

export function DataTable<T extends Record<string, unknown>>({
  columns, rows, rowKey, isLoading, loadingText, emptyText,
  title, actions, search, initialSort, sortable, pageSize,
  minWidth = 640, card, rowClassName, onRowClick, rowTestId,
}: DataTableProps<T>) {
  const { t } = useTranslation();
  const canSort = sortable ?? initialSort != null;
  const { processed, sortKey, sortDir, toggleSort } = useTableState<T>(rows, initialSort);
  const sorted = canSort ? processed : rows ?? [];

  const paginated = pageSize != null;
  const total = sorted.length;
  const totalPages = paginated ? Math.max(1, Math.ceil(total / pageSize)) : 1;
  const [page, setPage] = useState(1);
  // Reset to the first page whenever the result set, sort, or search changes.
  useEffect(() => setPage(1), [search?.value, sortKey, sortDir, total]);
  const safePage = Math.min(page, totalPages);
  const pageRows = paginated
    ? sorted.slice((safePage - 1) * pageSize, safePage * pageSize)
    : sorted;

  const hasHeader = title != null || search != null || actions != null;
  const wrapCard = card ?? hasHeader;

  const content = (
    <>
      {hasHeader && (
        <div className="flex items-center justify-between mb-4 gap-4">
          {title != null ? <p className="text-xl font-semibold">{title}</p> : <span />}
          <div className="flex items-center gap-3">
            {actions}
            {search && (
              <div className="relative w-64">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder={search.placeholder}
                  value={search.value}
                  onChange={(e) => search.onChange(e.target.value)}
                  className="pl-9"
                />
              </div>
            )}
          </div>
        </div>
      )}

      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-sm" style={{ minWidth }}>
          <thead>
            <tr className="border-b border-border bg-muted/50">
              {columns.map((col) => {
                const alignCls = col.align === "right" ? "text-right" : "text-left";
                const colSortable = canSort && col.sortable !== false;
                return (
                  <th key={col.key} className={`px-3 ${colSortable ? "py-0" : "py-2"} font-medium ${alignCls}`}>
                    {colSortable ? (
                      <button
                        onClick={() => toggleSort(col.key)}
                        className="flex items-center gap-1 py-2 hover:text-foreground transition-colors w-full"
                        style={{ justifyContent: col.align === "right" ? "flex-end" : "flex-start" }}
                      >
                        {col.header}
                        {sortKey === col.key && (
                          sortDir === "asc"
                            ? <ArrowUp className="h-3 w-3" />
                            : <ArrowDown className="h-3 w-3" />
                        )}
                      </button>
                    ) : col.header}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-8 text-center text-muted-foreground">
                  {loadingText ?? t("table.loading")}
                </td>
              </tr>
            ) : total === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-8 text-center text-muted-foreground">
                  {emptyText ?? t("table.empty")}
                </td>
              </tr>
            ) : (
              pageRows.map((row) => (
                <tr
                  key={rowKey(row)}
                  data-testid={rowTestId?.(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={`border-b border-border last:border-0 hover:bg-muted/30${
                    onRowClick ? " cursor-pointer" : ""
                  }${rowClassName ? ` ${rowClassName(row)}` : ""}`}
                >
                  {columns.map((col) => (
                    <td key={col.key} className={`px-3 py-2${col.align === "right" ? " text-right" : ""}${col.className ? ` ${col.className}` : ""}`}>
                      {col.cell ? col.cell(row) : defaultCell(row[col.key])}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {paginated && rows && (
        <div className="flex items-center justify-between mt-3">
          <p className="text-xs text-muted-foreground">
            {total === 0
              ? "0"
              : t("table.range", {
                  from: (safePage - 1) * pageSize + 1,
                  to: Math.min(safePage * pageSize, total),
                  total,
                })}
          </p>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" aria-label={t("pagination.prev")}
                onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={safePage === 1}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-xs text-muted-foreground tabular-nums">{safePage} / {totalPages}</span>
              <Button variant="outline" size="sm" aria-label={t("pagination.next")}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={safePage === totalPages}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
      )}
    </>
  );

  return wrapCard ? <Card className="p-6">{content}</Card> : content;
}
