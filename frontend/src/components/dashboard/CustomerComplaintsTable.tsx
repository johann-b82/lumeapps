/**
 * CustomerComplaintsTable — verification table for the Reklamationen view.
 *
 * Mirrors QualityFindingsTable structure (sortable columns, search,
 * pagination, native-title status tooltip) but the columns are tuned for
 * complaints: art badge is gone (all rows are KUNRE/KUN RE) and the two
 * quantities (Menge / akzeptierte Menge) take its place.
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
import {
  fetchCustomerComplaintsList,
  type ComplaintType,
  type CustomerComplaintRow,
} from "@/lib/api";
import { qualityKeys } from "@/lib/queryKeys";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";
import { useTableState } from "@/hooks/useTableState";

const PAGE_SIZE = 50;

const STATUS_FLAG_COLOR: Record<string, string> = {
  green: "#16a34a",
  yellow: "#eab308",
  red: "#dc2626",
};
const STATUS_FLAG_RE = /^isignal_flag_([a-z]+)$/i;

function StatusDot({ value }: { value: string | null }) {
  if (!value) return <span className="text-muted-foreground">—</span>;
  const m = STATUS_FLAG_RE.exec(value.trim());
  const colour = m ? STATUS_FLAG_COLOR[m[1].toLowerCase()] : undefined;
  if (!colour) {
    return (
      <span className="font-mono text-xs text-muted-foreground" title={value}>
        {value}
      </span>
    );
  }
  return (
    <span
      title={value}
      aria-label={value}
      className="inline-block h-3 w-3 rounded-full ring-1 ring-border align-middle"
      style={{ backgroundColor: colour }}
    />
  );
}

type ComplaintRow = CustomerComplaintRow & Record<string, unknown>;

interface CustomerComplaintsTableProps {
  complaintType: ComplaintType;
}

export function CustomerComplaintsTable({
  complaintType,
}: CustomerComplaintsTableProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const [search, setSearch] = useState("");

  const { range } = useDateRange();
  const date_from = toApiDate(range.from);
  const date_to = toApiDate(range.to);

  const { data, isLoading } = useQuery({
    queryKey: qualityKeys.complaintsList(date_from, date_to, complaintType),
    queryFn: () =>
      fetchCustomerComplaintsList({
        date_from,
        date_to,
        complaint_type: complaintType,
      }),
  });

  const filtered: ComplaintRow[] | undefined = data
    ?.filter((row) => {
      if (!search.trim()) return true;
      const needle = search.toLowerCase();
      return [
        row.report_nr,
        row.issuer,
        row.customer_name,
        row.customer_id,
        row.designation,
        row.status_code,
      ]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle));
    })
    .map((r) => r as ComplaintRow);

  const { processed, sortKey, sortDir, toggleSort } = useTableState<ComplaintRow>(
    filtered,
    { key: "report_date", dir: "desc" },
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

  const formatQty = (n: number | null) =>
    n == null ? "—" : new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(n);

  const columns = [
    { key: "report_nr",         label: t("quality.table.reportNr"),    align: "left" as const },
    { key: "report_date",       label: t("quality.table.date"),        align: "left" as const },
    { key: "customer_name",     label: t("quality.table.source"),      align: "left" as const },
    { key: "designation",       label: t("quality.table.designation"), align: "left" as const },
    { key: "quantity",          label: t("quality.table.quantity"),    align: "right" as const },
    { key: "accepted_quantity", label: t("quality.table.acceptedQty"), align: "right" as const },
    { key: "issuer",            label: t("quality.table.issuer"),      align: "left" as const },
    { key: "status_code",       label: t("quality.table.status"),      align: "left" as const },
  ];

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <p className="text-xl font-semibold">
          {t(`quality.complaintsTable.titleByType.${complaintType}`)}
        </p>
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
        <table className="w-full min-w-[960px] text-sm">
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
                <tr key={row.report_nr} className="border-b border-border last:border-0 hover:bg-muted/30">
                  <td className="px-3 py-2 font-mono text-xs">{row.report_nr}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{formatDate(row.report_date)}</td>
                  <td className="px-3 py-2">
                    {row.customer_name ?? "—"}
                    {row.customer_id && (
                      <span className="text-xs text-muted-foreground ml-1">
                        ({row.customer_id})
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground max-w-md truncate">
                    {row.designation ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatQty(row.quantity)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatQty(row.accepted_quantity)}</td>
                  <td className="px-3 py-2">{row.issuer ?? "—"}</td>
                  <td className="px-3 py-2">
                    <StatusDot value={row.status_code} />
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
