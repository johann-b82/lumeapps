/**
 * Gemeinsame Bausteine der HR-Seiten (Schulungen, Onboarding):
 * einklappbarer Abschnitt als Karte und die dezente Tabellen-Kopfzelle.
 */
import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

export function Klappbar({
  titel,
  anzahl,
  icon,
  offenStart = true,
  children,
}: {
  titel: string;
  anzahl?: number;
  icon?: ReactNode;
  offenStart?: boolean;
  children: ReactNode;
}) {
  const [offen, setOffen] = useState(offenStart);
  return (
    <div className="overflow-hidden rounded-xl border bg-card shadow-sm">
      <button
        type="button"
        onClick={() => setOffen((v) => !v)}
        aria-expanded={offen}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors
                   hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2
                   focus-visible:ring-ring focus-visible:ring-inset"
      >
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${
            offen ? "" : "-rotate-90"
          }`}
          aria-hidden="true"
        />
        {icon}
        <span className="font-medium">{titel}</span>
        {anzahl !== undefined && (
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs tabular-nums text-muted-foreground">
            {anzahl}
          </span>
        )}
      </button>
      {offen && <div className="overflow-x-auto border-t">{children}</div>}
    </div>
  );
}

export function Th({
  children,
  rechts,
}: {
  children: ReactNode;
  rechts?: boolean;
}) {
  return (
    <th
      className={`px-4 py-2 text-xs font-medium tracking-wide text-muted-foreground uppercase ${
        rechts ? "text-right" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}
