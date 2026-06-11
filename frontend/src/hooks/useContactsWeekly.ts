import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import { salesKeys } from "@/lib/queryKeys";

export interface ContactsWeeklyEmployeeBucket {
  erstkontakte: number;
  // v1.51: interessenten dropped from the per-employee bucket — the
  // Adressen/Interessenten source has no rep column. See
  // ``ContactsWeeklyWeek.interessenten`` for the new week-level total.
  visits: number;
  // v1.52: ONL (online meeting) count — rendered as a stacked segment
  // alongside ``visits`` (ORT) in the Besuche chart.
  onl?: number;
  angebote: number;
  // v1.56-b: weekly €-volume per rep from the auftraege table — rendered
  // as the 5th bar chart in the Vertriebsaktivität card.
  orders_eur?: number;
}

export interface ContactsWeeklyWeek {
  iso_year: number;
  iso_week: number;
  label: string;
  // v1.51: global Interessenten count for this week (Adress-Nr/Datum
  // Save grouped by ISO week). Not aggregated per rep.
  interessenten: number;
  // Keyed by Wer token (e.g. "GUENDEL"). v1.42: dropped Personio binding.
  per_employee: Record<string, ContactsWeeklyEmployeeBucket>;
}

export interface ContactsWeeklyResponse {
  weeks: ContactsWeeklyWeek[];
}

export function useContactsWeekly(from: string, to: string) {
  return useQuery<ContactsWeeklyResponse>({
    queryKey: salesKeys.contactsWeekly(from, to),
    queryFn: () =>
      apiClient<ContactsWeeklyResponse>(
        `/api/data/sales/contacts-weekly?from=${from}&to=${to}`,
      ),
    enabled: Boolean(from && to),
  });
}
