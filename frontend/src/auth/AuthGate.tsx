import { useEffect, type ReactNode } from "react";
import { useLocation } from "wouter";

import { useAuth } from "./useAuth";
import { FullPageSpinner } from "./FullPageSpinner";

/**
 * Route guard per D-05:
 *   - While the initial hydration runs, shows <FullPageSpinner>.
 *   - Unauthed on a non-/login path → redirect to /login.
 *   - Authed on /login → redirect to /.
 *
 * Rendering of children proceeds in all other cases; nested <Switch>
 * components handle actual route selection. This keeps AuthGate
 * decoupled from route definitions.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const { isLoading, user } = useAuth();
  const [location, setLocation] = useLocation();

  useEffect(() => {
    if (isLoading) return;
    if (!user && location !== "/login") {
      setLocation("/login");
    } else if (user && location === "/login") {
      setLocation("/");
    }
  }, [isLoading, user, location, setLocation]);

  if (isLoading) return <FullPageSpinner />;
  return <>{children}</>;
}
