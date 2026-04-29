import { useContext } from "react";

import { AuthContext, type AuthState, type Role } from "./AuthContext";

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}

export function useRole(): Role | null {
  return useAuth().role;
}
