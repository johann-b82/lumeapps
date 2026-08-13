/**
 * StockOrderTopTable — "Bestellung auf Lager – Top 20 Artikel des Jahres".
 *
 * Slow-moving Lagerartikel (Artikelnr prefix "L") with no stock movement in
 * the last 4 weeks, ranked by tied-up capital (current stock × latest
 * purchase price). Read-only, top-N (no pagination/search — the list is
 * short by design). Data comes from GET /api/procurement/stock-orders/top.
 */
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/card";
import { fetchTopStockOrders } from "@/lib/api";
import { procurementKeys } from "@/lib/queryKeys";

const LIMIT = 20;

export function StockOrderTopTable() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";

  const { data, isLoading, isError } = useQuery({
    queryKey: procurementKeys.stockOrdersTop(LIMIT),
    queryFn: () => fetchTopStockOrders({ limit: LIMIT }),
  });

  const eur = new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
  const qtyFmt = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
  const dateFmt = (d: string | null) =>
    d
      ? new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(
          new Date(d),
        )
      : "—";

  const maxValue = data && data.length ? data[0].value : 0;
  const totalValue = data?.reduce((s, r) => s + r.value, 0) ?? 0;

  return (
    <Card className="p-6">
      <div className="flex items-baseline justify-between mb-1 gap-4 flex-wrap">
        <p className="text-xl font-semibold">
          {t("procurement.stockOrders.title")}
        </p>
        {data && data.length > 0 && (
          <p className="text-sm text-muted-foreground">
            {t("procurement.stockOrders.totalLabel")}{" "}
            <span className="font-semibold text-foreground tabular-nums">
              {eur.format(totalValue)}
            </span>
          </p>
        )}
      </div>
      <p className="text-sm text-muted-foreground mb-4">
        {t("procurement.stockOrders.subtitle")}
      </p>

      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="px-3 py-2 text-right font-medium w-10">#</th>
              <th className="px-3 py-2 text-left font-medium">
                {t("procurement.stockOrders.col.article")}
              </th>
              <th className="px-3 py-2 text-left font-medium">
                {t("procurement.stockOrders.col.name")}
              </th>
              <th className="px-3 py-2 text-right font-medium">
                {t("procurement.stockOrders.col.stock")}
              </th>
              <th className="px-3 py-2 text-right font-medium">
                {t("procurement.stockOrders.col.price")}
              </th>
              <th className="px-3 py-2 text-left font-medium whitespace-nowrap">
                {t("procurement.stockOrders.col.lastMovement")}
              </th>
              <th className="px-3 py-2 text-right font-medium">
                {t("procurement.stockOrders.col.value")}
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-muted-foreground">
                  {t("quality.table.loading")}
                </td>
              </tr>
            ) : isError ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-destructive">
                  {t("procurement.stockOrders.loadError")}
                </td>
              </tr>
            ) : !data || data.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-muted-foreground">
                  {t("procurement.stockOrders.empty")}
                </td>
              </tr>
            ) : (
              data.map((row) => (
                <tr
                  key={row.article_number}
                  className="border-b border-border last:border-0 hover:bg-muted/30"
                >
                  <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                    {row.rank}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">
                    {row.article_number}
                  </td>
                  <td className="px-3 py-2 max-w-xs truncate">
                    {row.article_name ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {qtyFmt.format(row.stock_qty)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                    {eur.format(row.unit_price)}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-muted-foreground text-xs">
                    {dateFmt(row.last_movement)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums font-medium">
                    <div className="flex items-center justify-end gap-2">
                      <span
                        className="hidden sm:block h-1.5 rounded-full bg-primary/60"
                        style={{
                          width: `${
                            maxValue > 0
                              ? Math.max(4, (row.value / maxValue) * 64)
                              : 0
                          }px`,
                        }}
                        aria-hidden
                      />
                      {eur.format(row.value)}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
