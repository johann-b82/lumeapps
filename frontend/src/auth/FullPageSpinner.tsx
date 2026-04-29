import { Loader2 } from "lucide-react";

/**
 * Full-screen loading indicator shown by <AuthGate> while the initial
 * silent-refresh + readMe hydration is in flight. Styled per
 * 29-UI-SPEC.md §"Full-Page Spinner" — Loader2, h-8 w-8, muted, centered
 * on a min-h-screen background.
 */
export function FullPageSpinner() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  );
}
