import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import { salesKeys } from "@/lib/queryKeys";

export interface TopCustomer {
  name: string;
  total_value: number;
}

export interface OrdersDistributionResponse {
  orders_per_week_per_rep: number;
  top3_share_pct: number;
  remaining_share_pct: number;
  top3_customers: TopCustomer[];
}

export function useOrdersDistribution(from: string, to: string) {
  return useQuery<OrdersDistributionResponse>({
    queryKey: salesKeys.ordersDistribution(from, to),
    queryFn: () =>
      apiClient<OrdersDistributionResponse>(
        `/api/data/sales/orders-distribution?from=${from}&to=${to}`,
      ),
    enabled: Boolean(from && to),
  });
}
