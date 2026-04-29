import { useQuery } from "@tanstack/react-query";
import { fetchSettings, type Settings } from "@/lib/api";

export function useSettings() {
  return useQuery<Settings>({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    staleTime: Infinity,
    gcTime: Infinity,
    retry: 1,
  });
}
