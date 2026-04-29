import type { ReactNode } from "react";

import { useRole } from "./useAuth";

/**
 * Renders children only when the current user's role is 'admin'.
 * For Viewer (and unauthenticated) returns null — callers that need a
 * distinct "hidden" vs "not allowed" UX should check useRole() directly.
 */
export function AdminOnly({ children }: { children: ReactNode }) {
  return useRole() === "admin" ? <>{children}</> : null;
}
