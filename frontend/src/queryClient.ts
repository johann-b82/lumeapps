import { QueryClient } from "@tanstack/react-query";

/**
 * Shared singleton QueryClient. Imported by both App.tsx (QueryClientProvider)
 * and bootstrap.ts (seeds ["settings"] cache during cold start per D-06).
 * Both must reference the SAME instance for cache seeding to work.
 */
export const queryClient = new QueryClient();
