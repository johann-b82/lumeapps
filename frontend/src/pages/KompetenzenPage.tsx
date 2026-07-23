import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Upload } from "lucide-react";

/**
 * HR › Kompetenzen. Qualifikationsmatrix je Abteilung.
 *
 * Gerüst: Navigation und Abteilungsauswahl stehen, der Inhalt folgt mit den
 * vier Excel-Dateien — die Spaltenstruktur der Matrizen bestimmt das
 * Datenmodell, deshalb ist hier bewusst noch nichts vorweggenommen.
 */

/** Die vier Matrizen. Reihenfolge wie vom Fachbereich genannt. */
const ABTEILUNGEN = ["produktion", "verwaltung", "safety", "quality"] as const;
type Abteilung = (typeof ABTEILUNGEN)[number];

export function KompetenzenPage() {
  const { t } = useTranslation();
  const [aktiv, setAktiv] = useState<Abteilung>("produktion");

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
      <h1 className="mb-1 text-lg font-semibold">{t("kompetenzen.title")}</h1>
      <p className="mb-5 text-sm text-muted-foreground">{t("kompetenzen.untertitel")}</p>

      <div className="mb-5 flex flex-wrap gap-1 rounded-lg border p-0.5" role="tablist">
        {ABTEILUNGEN.map((a) => (
          <button
            key={a}
            type="button"
            role="tab"
            aria-selected={aktiv === a}
            onClick={() => setAktiv(a)}
            className={`rounded-md px-4 py-1.5 text-sm transition-colors ${
              aktiv === a
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted"
            }`}
          >
            {t(`kompetenzen.abteilung.${a}`)}
          </button>
        ))}
      </div>

      <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-20 text-center">
        <Upload className="h-10 w-10 text-muted-foreground" aria-hidden="true" />
        <p className="text-sm font-medium">
          {t("kompetenzen.leer.title", { abteilung: t(`kompetenzen.abteilung.${aktiv}`) })}
        </p>
        <p className="max-w-md text-sm text-muted-foreground">{t("kompetenzen.leer.hinweis")}</p>
      </div>
    </div>
  );
}
