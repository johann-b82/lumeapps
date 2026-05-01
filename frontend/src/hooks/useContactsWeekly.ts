import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import { salesKeys } from "@/lib/queryKeys";

export interface ContactsWeeklyEmployeeBucket {
  erstkontakte: number;
  interessenten: number;
  visits: number;
  angebote: number;
}

export interface ContactsWeeklyWeek {
  iso_year: number;
  iso_week: number;
  label: string;
  per_employee: Record<number, ContactsWeeklyEmployeeBucket>;
}

export interface ContactsWeeklyResponse {
  weeks: ContactsWeeklyWeek[];
  employees: Record<number, string>;
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
