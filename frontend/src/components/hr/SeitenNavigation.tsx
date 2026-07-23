import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { ArrowLeft, Home } from "lucide-react";

/**
 * Zurück- und Start-Schaltfläche für die HR-Unterseiten.
 *
 * "Zurück" führt bewusst auf eine feste Route statt über die Browser-Historie:
 * wer die Seite über einen Link oder ein Lesezeichen betritt, hat keine
 * Historie, und history.back() würde ihn aus der Anwendung heraustragen.
 */
export function SeitenNavigation({ zurueckNach = "/hr/home" }: { zurueckNach?: string }) {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();

  const stil =
    "inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors " +
    "hover:text-foreground focus-visible:outline-none focus-visible:ring-2 " +
    "focus-visible:ring-ring rounded-md";

  return (
    <div className="mb-3 flex items-center gap-4">
      <button type="button" className={stil} onClick={() => setLocation(zurueckNach)}>
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        {t("nav.zurueck")}
      </button>
      <button type="button" className={stil} onClick={() => setLocation("/")}>
        <Home className="h-4 w-4" aria-hidden="true" />
        {t("nav.start")}
      </button>
    </div>
  );
}
