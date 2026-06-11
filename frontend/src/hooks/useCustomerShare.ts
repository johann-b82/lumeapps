import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import { salesKeys } from "@/lib/queryKeys";

export type CustomerShareSource = "auftraege" | "revenues";

export interface CustomerShareEntry {
  name: string;
  total_value: number;
  share_pct: number;
}

export interface CustomerShareResponse {
  source: CustomerShareSource;
  top_n: number;
  total_value: number;
  top_share_pct: number;
  remaining_share_pct: number;
  top_customers: CustomerShareEntry[];
}

/**
 * v1.56-c — Top-N customer share for the Kundenanteil waterfall card.
 * Source = ``"auftraege"`` (order book) or ``"revenues"`` (RG/GS net).
 * Default top_n=14 matches the card's expand-to-14 toggle.
 */
export function useCustomerShare(
  source: CustomerShareSource,
  from: string,
  to: string,
  topN: number = 14,
) {
  return useQuery<CustomerShareResponse>({
    queryKey: salesKeys.customerShare(source, from, to),
    queryFn: () =>
      apiClient<CustomerShareResponse>(
        `/api/data/sales/customer-share?source=${source}&top_n=${topN}&from=${from}&to=${to}`,
      ),
    enabled: Boolean(from && to),
  });
}
