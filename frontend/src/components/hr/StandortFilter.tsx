/**
 * Standort-Filter für HR-Listen — gleiche Chips + Vorauswahl wie das Organigramm
 * (siehe OrganigrammPage). Mehrfachauswahl; leere Auswahl = alle Standorte.
 */
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

/** Vorbelegte Haupt-Standorte (wie im Organigramm); Remote/übrige erst auf Klick. */
export const DEFAULT_OFFICES = ["Hamburg", "Memmingen"];

/**
 * Ermittelt die vorhandenen Standorte und filtert `items` nach der Auswahl.
 * `getOffice` liefert den Standort eines Eintrags (null = kein Standort).
 */
export function useStandortFilter<T>(
  items: T[] | undefined,
  getOffice: (item: T) => string | null,
) {
  const offices = useMemo(() => {
    const set = new Set<string>();
    items?.forEach((i) => {
      const o = getOffice(i);
      if (o) set.add(o);
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [items, getOffice]);

  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(DEFAULT_OFFICES),
  );

  const toggle = (office: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(office)) next.delete(office);
      else next.add(office);
      return next;
    });

  const filtered = useMemo(() => {
    if (!items) return [];
    if (selected.size === 0) return items;
    return items.filter((i) => {
      const o = getOffice(i);
      return o != null && selected.has(o);
    });
  }, [items, selected, getOffice]);

  return { offices, selected, toggle, filtered };
}

/** Chip-Reihe zum Standort-Filtern (Darstellung wie im Organigramm). */
export function StandortChips({
  offices,
  selected,
  onToggle,
}: {
  offices: string[];
  selected: Set<string>;
  onToggle: (office: string) => void;
}) {
  const { t } = useTranslation();
  if (offices.length === 0) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs text-muted-foreground">{t("hr.organigramm.office")}</span>
      <div
        className="flex flex-wrap gap-2"
        role="group"
        aria-label={t("hr.organigramm.office")}
      >
        {offices.map((o) => {
          const on = selected.has(o);
          return (
            <button
              key={o}
              type="button"
              onClick={() => onToggle(o)}
              aria-pressed={on}
              className={`rounded-full border px-3 py-1 text-sm transition-colors
                          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
                          ${
                            on
                              ? "bg-primary text-primary-foreground border-primary"
                              : "bg-transparent text-muted-foreground border-border hover:bg-muted"
                          }`}
            >
              {o}
            </button>
          );
        })}
      </div>
    </div>
  );
}
