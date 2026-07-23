import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, Loader2, Upload } from "lucide-react";
import {
  fetchMatrix,
  fetchMatrizen,
  kompetenzImportCommit,
  kompetenzImportPreview,
  KOMPETENZ_BEREICHE,
  type KompetenzBereich,
  type KompetenzImportVorschau,
  type Matrix,
  type MatrixUebersicht,
  type Qualifikation,
} from "@/lib/kompetenzApi";
import { hrKpiKeys } from "@/lib/queryKeys";
import { Klappbar, Th } from "@/components/hr/Klappbar";

/** Erfüllungsgrad → Farbe. Rot = Lücke, Grün = erfüllt. */
function gradFarbe(grad: number): string {
  if (grad >= 100) return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400";
  if (grad >= 75) return "bg-lime-500/15 text-lime-700 dark:text-lime-400";
  if (grad >= 50) return "bg-amber-500/15 text-amber-700 dark:text-amber-400";
  if (grad > 0) return "bg-orange-500/15 text-orange-700 dark:text-orange-400";
  return "bg-destructive/15 text-destructive";
}

/** Eine Zelle: Anforderungslevel als Ziffer, Erfüllungsgrad farbig. */
function ZelleAnzeige({
  level,
  grad,
}: {
  level: number | null;
  grad: number | null;
}) {
  if (level === null && grad === null) {
    return <span className="text-muted-foreground/40">·</span>;
  }
  return (
    <span className="inline-flex items-center gap-1">
      {level !== null && level > 0 && (
        <span className="rounded bg-muted px-1 text-[10px] tabular-nums text-muted-foreground">
          {level}
        </span>
      )}
      {grad !== null && (
        <span className={`rounded px-1 text-[11px] tabular-nums ${gradFarbe(grad)}`}>
          {grad}
        </span>
      )}
    </span>
  );
}

/** Die Matrix selbst — Zeilen nach Kategorie gruppiert, Spalten sind Personen. */
function MatrixTabelle({ matrix }: { matrix: Matrix }) {
  const { t } = useTranslation();
  const [nurLuecken, setNurLuecken] = useState(false);

  const gruppen = useMemo(() => {
    const map = new Map<string, Qualifikation[]>();
    for (const q of matrix.qualifikationen) {
      const k = q.kategorie ?? t("kompetenzen.ohneKategorie");
      const liste = map.get(k) ?? [];
      liste.push(q);
      map.set(k, liste);
    }
    return [...map.entries()];
  }, [matrix.qualifikationen, t]);

  /** Zellen einer Zeile nach Person-ID, damit die Spaltenordnung stimmt. */
  const zellenIndex = useMemo(() => {
    const m = new Map<number, Map<number, { al: number | null; e: number | null }>>();
    for (const q of matrix.qualifikationen) {
      const proPerson = new Map<number, { al: number | null; e: number | null }>();
      for (const z of q.zellen) {
        proPerson.set(z.person_id, { al: z.anforderungslevel, e: z.erfuellungsgrad });
      }
      m.set(q.id, proPerson);
    }
    return m;
  }, [matrix.qualifikationen]);

  return (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={nurLuecken}
            onChange={(e) => setNurLuecken(e.target.checked)}
            className="h-3.5 w-3.5 rounded border-input"
          />
          {t("kompetenzen.nurLuecken")}
        </label>
        <span className="text-xs text-muted-foreground">{t("kompetenzen.legende")}</span>
      </div>

      {gruppen.map(([kategorie, zeilen]) => {
        const gezeigt = nurLuecken
          ? zeilen.filter((q) =>
              q.zellen.some(
                (z) =>
                  z.anforderungslevel !== null &&
                  z.anforderungslevel > 0 &&
                  (z.erfuellungsgrad ?? 0) < 100,
              ),
            )
          : zeilen;
        if (gezeigt.length === 0) return null;

        return (
          <section key={kategorie} className="mb-4">
            <Klappbar titel={kategorie} anzahl={gezeigt.length}>
              {/* Die Matrix ist von Natur aus breit (bis 31 Personen). Der
                  Rahmen scrollt daher selbst, statt die Seite zu dehnen; die
                  Qualifikationsspalte bleibt dabei stehen. */}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/20">
                      <th
                        className="sticky left-0 z-10 min-w-[16rem] bg-muted/40 px-4 py-2
                                   text-left text-xs font-medium text-muted-foreground backdrop-blur"
                      >
                        {t("kompetenzen.qualifikation")}
                      </th>
                      <Th rechts>{t("kompetenzen.schnitt")}</Th>
                      {matrix.personen.map((p) => (
                        <th
                          key={p.id}
                          className="px-2 py-2 text-center text-xs font-medium
                                     text-muted-foreground whitespace-nowrap"
                          title={p.employee_id ? undefined : t("kompetenzen.ohneTreffer")}
                        >
                          {p.name}
                          {!p.employee_id && (
                            <span className="ml-1 text-amber-500" aria-hidden="true">
                              *
                            </span>
                          )}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {gezeigt.map((q) => {
                      const proPerson = zellenIndex.get(q.id);
                      return (
                        <tr
                          key={q.id}
                          className="border-b border-border/40 transition-colors last:border-0 hover:bg-muted/30"
                        >
                          <td className="sticky left-0 z-10 bg-card px-4 py-1.5">
                            {q.nr !== null && (
                              <span className="mr-2 text-xs tabular-nums text-muted-foreground">
                                {q.nr}
                              </span>
                            )}
                            {q.bezeichnung}
                          </td>
                          <td className="px-4 py-1.5 text-right tabular-nums text-muted-foreground">
                            {q.durchschnitt === null ? "—" : `${q.durchschnitt}%`}
                          </td>
                          {matrix.personen.map((p) => {
                            const z = proPerson?.get(p.id);
                            return (
                              <td key={p.id} className="px-2 py-1.5 text-center">
                                <ZelleAnzeige
                                  level={z?.al ?? null}
                                  grad={z?.e ?? null}
                                />
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Klappbar>
          </section>
        );
      })}
    </>
  );
}

/** Kennzahlen je Person — beantwortet "wer hat die größten Lücken". */
function PersonenPanel({ matrix }: { matrix: Matrix }) {
  const { t } = useTranslation();
  const sortiert = useMemo(
    () => [...matrix.personen].sort((a, b) => b.luecken - a.luecken),
    [matrix.personen],
  );

  return (
    <section className="mb-6">
      <Klappbar titel={t("kompetenzen.personen.title")} anzahl={sortiert.length} offenStart={false}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/20">
              <Th>{t("kompetenzen.personen.name")}</Th>
              <Th rechts>{t("kompetenzen.personen.schnitt")}</Th>
              <Th rechts>{t("kompetenzen.personen.luecken")}</Th>
            </tr>
          </thead>
          <tbody>
            {sortiert.map((p) => (
              <tr
                key={p.id}
                className="border-b border-border/40 transition-colors last:border-0 hover:bg-muted/30"
              >
                <td className="px-4 py-1.5">
                  {p.name}
                  {!p.employee_id && (
                    <span className="ml-2 rounded-md bg-amber-500/15 px-2 py-0.5 text-xs text-amber-600 dark:text-amber-400">
                      {t("kompetenzen.ohneTreffer")}
                    </span>
                  )}
                </td>
                <td className="px-4 py-1.5 text-right tabular-nums">
                  {p.durchschnitt === null ? "—" : `${p.durchschnitt}%`}
                </td>
                <td className="px-4 py-1.5 text-right tabular-nums">
                  {p.luecken > 0 ? (
                    <span className="rounded-md bg-amber-500/15 px-2 py-0.5 text-amber-600 dark:text-amber-400">
                      {p.luecken}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">0</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Klappbar>
    </section>
  );
}

/** Ergebnis von Vorschau bzw. Übernahme. */
function Vorschau({
  vorschau,
  uebernommen,
}: {
  vorschau: KompetenzImportVorschau;
  uebernommen: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className="mt-3 rounded-xl border bg-card p-4 text-sm shadow-sm">
      <p className="mb-2 font-medium">
        {uebernommen ? t("kompetenzen.import.uebernommen") : t("kompetenzen.import.vorschau")} ·{" "}
        <span className="font-mono text-xs text-muted-foreground">{vorschau.dateiname}</span>
      </p>
      <ul className="space-y-1">
        {vorschau.matrizen.map((m) => (
          <li key={m.blatt}>
            <span className="font-medium">{m.blatt}</span>{" "}
            <span className="text-muted-foreground">
              {t("kompetenzen.import.zahlen", {
                qualifikationen: m.qualifikationen,
                personen: m.personen,
                bewertungen: m.bewertungen,
              })}
            </span>
            {m.nicht_zugeordnet.length > 0 && (
              <div className="mt-0.5 flex gap-2 text-xs text-amber-600 dark:text-amber-400">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span>
                  {t("kompetenzen.import.ohneTreffer")}: {m.nicht_zugeordnet.join(", ")}
                </span>
              </div>
            )}
          </li>
        ))}
      </ul>
      {vorschau.warnungen.map((w) => (
        <p key={w} className="mt-2 text-xs text-muted-foreground">
          {w}
        </p>
      ))}
    </div>
  );
}

/** Import einer Bereichsdatei. */
function ImportPanel({ bereich }: { bereich: KompetenzBereich }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const eingabe = useRef<HTMLInputElement>(null);
  const [datei, setDatei] = useState<File | null>(null);
  const [vorschau, setVorschau] = useState<KompetenzImportVorschau | null>(null);
  const [uebernommen, setUebernommen] = useState(false);

  const pruefen = useMutation({
    mutationFn: (f: File) => kompetenzImportPreview(bereich, f),
    onSuccess: (v) => {
      setVorschau(v);
      setUebernommen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const uebernehmen = useMutation({
    mutationFn: (f: File) => kompetenzImportCommit(bereich, f),
    onSuccess: (v) => {
      setVorschau(v);
      setUebernommen(true);
      toast.success(t("kompetenzen.import.erfolg", { count: v.matrizen.length }));
      qc.invalidateQueries({ queryKey: hrKpiKeys.kompetenzMatrizen() });
      qc.invalidateQueries({ queryKey: ["hr", "kompetenzen", "matrix"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const laeuft = pruefen.isPending || uebernehmen.isPending;

  return (
    <section className="mb-6">
      <Klappbar
        titel={t("kompetenzen.import.title")}
        icon={<Upload className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
        offenStart={false}
      >
        <div className="px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={eingabe}
              type="file"
              accept=".xlsx,.xlsm"
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                setDatei(f);
                setVorschau(null);
                if (f) pruefen.mutate(f);
              }}
              className="text-sm file:mr-3 file:rounded-md file:border-0 file:bg-muted
                         file:px-3 file:py-1.5 file:text-sm"
            />
            <button
              type="button"
              disabled={!datei || laeuft || !vorschau}
              onClick={() => datei && uebernehmen.mutate(datei)}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-1.5 text-sm
                         text-primary-foreground disabled:opacity-50
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {laeuft && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              {t("kompetenzen.import.aktion")}
            </button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {t("kompetenzen.import.hinweis")}
          </p>
          {vorschau && <Vorschau vorschau={vorschau} uebernommen={uebernommen} />}
        </div>
      </Klappbar>
    </section>
  );
}

/**
 * HR › Kompetenzen. Qualifikationsmatrix je Bereich.
 *
 * Quality bringt drei Blätter mit (QM, CS, QS), die anderen Bereiche eins —
 * die Blattauswahl erscheint deshalb nur, wenn es mehr als eines gibt.
 */
export function KompetenzenPage() {
  const { t } = useTranslation();
  const [bereich, setBereich] = useState<KompetenzBereich>("produktion");
  const [matrixId, setMatrixId] = useState<number | null>(null);

  const { data: matrizen, isLoading } = useQuery({
    queryKey: hrKpiKeys.kompetenzMatrizen(),
    queryFn: fetchMatrizen,
  });

  const imBereich: MatrixUebersicht[] = useMemo(
    () => (matrizen ?? []).filter((m) => m.bereich === bereich),
    [matrizen, bereich],
  );
  const aktiv = imBereich.find((m) => m.id === matrixId) ?? imBereich[0];

  const { data: matrix, isLoading: laedtMatrix } = useQuery({
    queryKey: hrKpiKeys.kompetenzMatrix(aktiv?.id ?? 0),
    queryFn: () => fetchMatrix(aktiv!.id),
    enabled: aktiv !== undefined,
  });

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
      <h1 className="mb-1 text-lg font-semibold">{t("kompetenzen.title")}</h1>
      <p className="mb-5 text-sm text-muted-foreground">{t("kompetenzen.untertitel")}</p>

      <div className="mb-5 flex flex-wrap gap-1 rounded-lg border p-0.5" role="tablist">
        {KOMPETENZ_BEREICHE.map((b) => (
          <button
            key={b}
            type="button"
            role="tab"
            aria-selected={bereich === b}
            onClick={() => {
              setBereich(b);
              setMatrixId(null);
            }}
            className={`rounded-md px-4 py-1.5 text-sm transition-colors ${
              bereich === b
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted"
            }`}
          >
            {t(`kompetenzen.abteilung.${b}`)}
          </button>
        ))}
      </div>

      <ImportPanel bereich={bereich} />

      {isLoading && (
        <div className="flex h-24 items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" />
        </div>
      )}

      {!isLoading && imBereich.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-20 text-center">
          <Upload className="h-10 w-10 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm font-medium">
            {t("kompetenzen.leer.title", { abteilung: t(`kompetenzen.abteilung.${bereich}`) })}
          </p>
          <p className="max-w-md text-sm text-muted-foreground">
            {t("kompetenzen.leer.hinweis")}
          </p>
        </div>
      )}

      {/* Blattauswahl nur bei mehreren Matrizen (Quality: QM, CS, QS). */}
      {imBereich.length > 1 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {imBereich.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => setMatrixId(m.id)}
              className={`rounded-md border px-3 py-1 text-xs transition-colors ${
                aktiv?.id === m.id ? "border-primary bg-primary/10" : "hover:bg-muted"
              }`}
            >
              {m.blatt}
            </button>
          ))}
        </div>
      )}

      {aktiv && (
        <p className="mb-4 text-xs text-muted-foreground">
          {aktiv.titel ?? aktiv.blatt}
          {aktiv.stand && ` · ${t("kompetenzen.stand", { datum: new Date(aktiv.stand).toLocaleDateString() })}`}
          {` · ${t("kompetenzen.umfang", { qualifikationen: aktiv.qualifikationen, personen: aktiv.personen })}`}
        </p>
      )}

      {laedtMatrix && (
        <div className="flex h-24 items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" />
        </div>
      )}

      {matrix && (
        <>
          <PersonenPanel matrix={matrix} />
          <MatrixTabelle matrix={matrix} />
        </>
      )}
    </div>
  );
}
