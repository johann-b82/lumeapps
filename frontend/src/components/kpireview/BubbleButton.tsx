import { useTranslation } from "react-i18next";
import { MessageSquareDashed } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/auth/useAuth";
import { useBubbleMode } from "@/contexts/BubbleModeContext";

/**
 * Global floating "Bubble" toggle — sits above the feedback button. When on,
 * every KPI chart accepts a region draw to place a bubble. Admin only.
 */
export function BubbleButton() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { active, toggle } = useBubbleMode();
  if (user?.role !== "admin") return null;

  return (
    <Button
      type="button"
      onClick={toggle}
      aria-pressed={active}
      aria-label={t("kpireview.bubble.mode")}
      variant={active ? "default" : "secondary"}
      // Stacked above the feedback button (bottom-5) — same right edge.
      className="fixed bottom-16 right-5 z-40 gap-2 shadow-lg"
    >
      <MessageSquareDashed className="h-4 w-4" aria-hidden />
      <span className="hidden sm:inline">
        {active ? t("kpireview.bubble.modeOn") : t("kpireview.bubble.mode")}
      </span>
    </Button>
  );
}
