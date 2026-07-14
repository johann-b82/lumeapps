/**
 * QualityInspectionList — per-booking verification table (v1.80).
 *
 * One row per raw AswQs2151 booking. A checkbox in the leading column
 * toggles whether the booking is counted in the KPI: checked = counted
 * (default), unchecked = excluded (row still visible but muted, and the
 * KPI cards / charts refresh with the excluded qty removed). The toggle
 * hits PATCH /api/quality/inspections/bookings/{id} and invalidates
 * every downstream inspection query.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import {
  Search,
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { cn } from "@/lib/utils";
import {
  fetchInspectionBookings,
  updateInspectionBooking,
  type InspectionBookingRow,
} from "@/lib/api";
import { qualityKeys } from "@/lib/queryKeys";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";
import { useTableState } from "@/hooks/useTableState";
import { useRole } from "@/auth/useAuth";

// Local include-checkbox — the base-ui Checkbox rendered as a thin blue
// bar on this size/density combo, so we swap in a plain button with a
// bold Check icon that reads at 20 px on a busy row.
function IncludeCheckbox({
  checked,
  disabled,
  onCheckedChange,
  label,
}: {
  checked: boolean;
  disabled?: boolean;
  onCheckedChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "h-5 w-5 rounded-sm border-2 border-primary flex items-center justify-center transition-colors",
        checked ? "bg-primary text-primary-foreground" : "bg-background",
        disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
      )}
    >
      {checked && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
    </button>
  );
}

const PAGE_SIZE = 50;

const SIZE_COLOR: Record<"large" | "small", string> = {
  large: "#2563eb",
  small: "#0d9488",
};

function SizeBadge({
  size,
  label,
}: {
  size: "large" | "small";
  label: string;
}) {
  const color = SIZE_COLOR[size];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"
      style={{ backgroundColor: `${color}1a`, color }}
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}

type BookingRow = InspectionBookingRow & Record<string, unknown>;
type SizeFilter = "all" | "large" | "small";

export function QualityInspectionList() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const role = useRole();
  const isAdmin = role === "admin";
  const [search, setSearch] = useState("");
  const [sizeFilter, setSizeFilter] = useState<SizeFilter>("all");
  const queryClient = useQueryClient();

  const { range } = useDateRange();
  const date_from = toApiDate(range.from);
  const date_to = toApiDate(range.to);

  const bookingsKey = qualityKeys.inspectionsBookings(date_from, date_to);
  const { data, isLoading } = useQuery({
    queryKey: bookingsKey,
    queryFn: () => fetchInspectionBookings({ date_from, date_to }),
  });

  const mutation = useMutation({
    mutationFn: ({ id, excluded }: { id: number; excluded: boolean }) =>
      updateInspectionBooking(id, excluded),
    // Optimistic: flip the row in the cache immediately so the checkbox
    // reacts without a round-trip. Roll back if the request errors.
    onMutate: async ({ id, excluded }) => {
      await queryClient.cancelQueries({ queryKey: bookingsKey });
      const previous =
        queryClient.getQueryData<InspectionBookingRow[]>(bookingsKey);
      queryClient.setQueryData<InspectionBookingRow[]>(
        bookingsKey,
        (rows) =>
          rows?.map((r) => (r.id === id ? { ...r, excluded } : r)) ?? rows,
      );
      return { previous };
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(bookingsKey, ctx.previous);
      toast.error(err instanceof Error ? err.message : String(err));
    },
    onSuccess: () => {
      // KPI cards, chart, aggregated list all depend on excluded state.
      queryClient.invalidateQueries({ queryKey: ["quality", "inspections"] });
    },
  });

  const filtered: BookingRow[] | undefined = data
    ?.filter((row) => sizeFilter === "all" || row.size_class === sizeFilter)
    .filter((row) => {
      if (!search.trim()) return true;
      const needle = search.toLowerCase();
      return [
        row.bezeichnung,
        row.produktgruppe,
        row.benutzer,
        row.fa,
        row.artikel,
      ]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle));
    })
    .map((r) => r as BookingRow);

  const { processed, sortKey, sortDir, toggleSort } = useTableState<BookingRow>(
    filtered,
    { key: "pruef_datum", dir: "desc" },
  );

  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(processed.length / PAGE_SIZE));
  useEffect(() => {
    setPage(1);
  }, [search, sizeFilter, sortKey, sortDir, data?.length]);
  const safePage = Math.min(page, totalPages);
  const pageRows = processed.slice(
    (safePage - 1) * PAGE_SIZE,
    safePage * PAGE_SIZE,
  );

  const excludedCount = (data ?? []).filter((r) => r.excluded).length;

  const formatDate = (d: string | null) => {
    if (!d) return "—";
    return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(
      new Date(d),
    );
  };
  const formatTime = (t: string | null) => {
    if (!t) return "";
    // t is "HH:MM:SS" — trim seconds for scan-density.
    return t.length >= 5 ? t.slice(0, 5) : t;
  };
  const formatNumber = (n: number) =>
    new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(n);

  const sizeLabels: Record<"large" | "small", string> = {
    large: t("quality.inspection.large.label"),
    small: t("quality.inspection.small.label"),
  };

  type Align = "left" | "right" | "center";
  const columns: Array<{ key: string; label: string; align: Align }> = [
    { key: "include",         label: "",                                       align: "center" },
    { key: "pruef_datum",     label: t("quality.inspectionList.date"),         align: "left" },
    { key: "benutzer",        label: t("quality.inspectionList.user"),         align: "left" },
    { key: "fa",              label: t("quality.inspectionList.fa"),           align: "left" },
    { key: "artikel",         label: t("quality.inspectionList.article"),      align: "left" },
    { key: "bezeichnung",     label: t("quality.inspectionList.name"),         align: "left" },
    { key: "size_class",      label: t("quality.inspectionList.sizeClass"),    align: "left" },
    { key: "produktgruppe",   label: t("quality.inspectionList.group"),        align: "left" },
    { key: "buchungs_menge",  label: t("quality.inspectionList.totalQty"),     align: "right" },
    { key: "ausschuss_menge", label: t("quality.inspectionList.scrapQty"),     align: "right" },
  ];

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4 gap-4 flex-wrap">
        <div className="flex items-baseline gap-3">
          <p className="text-xl font-semibold">
            {t("quality.inspectionList.title")}
          </p>
          {excludedCount > 0 && (
            <span className="text-xs text-muted-foreground">
              {t("quality.inspectionList.excludedCount", {
                count: excludedCount,
              })}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <SegmentedControl<SizeFilter>
            segments={[
              { value: "all", label: t("quality.inspectionList.filter.all") },
              { value: "large", label: t("quality.inspection.large.label") },
              { value: "small", label: t("quality.inspection.small.label") },
            ]}
            value={sizeFilter}
            onChange={setSizeFilter}
            aria-label={t("quality.inspectionList.filter.label")}
          />
          <div className="relative w-72">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={t("quality.inspectionList.search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[1120px] text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-3 py-0 font-medium text-${col.align} ${
                    col.key === "include" ? "w-10" : ""
                  }`}
                >
                  {col.key === "include" ? (
                    <div
                      className="py-2 text-xs text-muted-foreground"
                      title={t("quality.inspectionList.includeHeader")}
                    >
                      ✓
                    </div>
                  ) : (
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
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-3 py-8 text-center text-muted-foreground"
                >
                  {t("quality.inspectionList.loading")}
                </td>
              </tr>
            ) : !processed.length ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-3 py-8 text-center text-muted-foreground"
                >
                  {t("quality.inspectionList.empty")}
                </td>
              </tr>
            ) : (
              pageRows.map((row) => {
                const included = !row.excluded;
                return (
                  <tr
                    key={row.id}
                    className={`border-b border-border last:border-0 hover:bg-muted/30 ${
                      row.excluded ? "opacity-60 line-through" : ""
                    }`}
                  >
                    <td className="px-3 py-2 text-center">
                      <div className="flex justify-center">
                        <IncludeCheckbox
                          checked={included}
                          disabled={!isAdmin || mutation.isPending}
                          onCheckedChange={(v) =>
                            mutation.mutate({
                              id: row.id,
                              excluded: !v,
                            })
                          }
                          label={
                            included
                              ? t("quality.inspectionList.excludeRow")
                              : t("quality.inspectionList.includeRow")
                          }
                        />
                      </div>
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {formatDate(row.pruef_datum)}
                      {row.pruef_zeit && (
                        <span className="text-xs text-muted-foreground ml-1">
                          {formatTime(row.pruef_zeit)}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {row.benutzer ?? "—"}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                      {row.fa ?? "—"}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                      {row.artikel ?? "—"}
                    </td>
                    <td className="px-3 py-2 max-w-md truncate">
                      {row.bezeichnung ?? "—"}
                    </td>
                    <td className="px-3 py-2">
                      <SizeBadge
                        size={row.size_class}
                        label={sizeLabels[row.size_class]}
                      />
                    </td>
                    <td className="px-3 py-2 text-muted-foreground font-mono text-xs">
                      {row.produktgruppe ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatNumber(row.buchungs_menge)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                      {formatNumber(row.ausschuss_menge)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {data && (
        <div className="flex items-center justify-between mt-3">
          <p className="text-xs text-muted-foreground">
            {processed.length === 0
              ? `0 ${t("quality.inspectionList.records")}`
              : `${(safePage - 1) * PAGE_SIZE + 1}–${Math.min(
                  safePage * PAGE_SIZE,
                  processed.length,
                )} / ${processed.length} ${t(
                  "quality.inspectionList.records",
                )}`}
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
