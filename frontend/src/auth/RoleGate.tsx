import type { ReactNode } from "react";

import { type Role } from "./AuthContext";
import { useRole } from "./useAuth";

/**
 * Renders children only when the current user's role is in `allow`.
 * Generalizes <AdminOnly> for multi-role gating (e.g. the FAIR/ATR modules
 * that admit both Admin and the interim QS role). Returns null otherwise.
 */
export function RoleGate({ allow, children }: { allow: Role[]; children: ReactNode }) {
  const role = useRole();
  return role && allow.includes(role) ? <>{children}</> : null;
}
