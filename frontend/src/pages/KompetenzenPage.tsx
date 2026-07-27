import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Info, Loader2, Pencil, Table2, X } from "lucide-react";
import {
  benenneKategorieUm,
  entfernePerson,
  entferneQualifikation,
  fetchMatrix,
  fetchMatrizen,
  fetchVerfuegbarePersonen,
  legePersonAn,
  legeQualifikationAn,
  setzeZelle,
  KOMPETENZ_BEREICHE,
  type KompetenzBereich,
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

/** Eine Zelle im Bearbeiten-Modus: Anforderungslevel als Auswahl, Grad als Zahl.
 *
 *  Gespeichert wird pro Zelle sofort — bei bis zu 31 Personen × 90 Zeilen wäre
 *  ein "Alles speichern" am Ende ein Berg unklarer ungesicherter Änderungen.
 *  Der Erfüllungsgrad geht erst beim Verlassen des Feldes raus, sonst käme
 *  jeder Tastendruck als eigener Aufruf an.
 */
function ZelleBearbeiten({
  matrixId,
  qualifikationId,
  personId,
  level,
  grad,
}: {
  matrixId: number;
  qualifikationId: number;
  personId: number;
  level: number | null;
  grad: number | null;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [entwurf, setEntwurf] = useState(grad === null ? "" : String(grad));

  const speichern = useMutation({
    mutationFn: (w: { al: number | null; e: number | null }) =>
      setzeZelle(matrixId, {
        qualifikation_id: qualifikationId,
        person_id: personId,
        anforderungslevel: w.al,
        erfuellungsgrad: w.e,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: hrKpiKeys.kompetenzMatrix(matrixId) });
    },
    onError: (e: Error) => {
      toast.error(e.message);
      setEntwurf(grad === null ? "" : String(grad)); // verworfenen Wert zurücksetzen
    },
  });

  const gradAbschicken = () => {
    const roh = entwurf.trim();
    if (roh === "") {
      if (grad !== null) speichern.mutate({ al: level, e: null });
      return;
    }
    const zahl = Number(roh);
    if (!Number.isFinite(zahl) || zahl < 0 || zahl > 100) {
      toast.error(t("kompetenzen.gradUngueltig"));
      setEntwurf(grad === null ? "" : String(grad));
      return;
    }
    const gerundet = Math.round(zahl);
    if (gerundet !== grad) speichern.mutate({ al: level, e: gerundet });
  };

  return (
    <span className="inline-flex items-center gap-0.5">
      <select
        value={level === null ? "" : String(level)}
        disabled={speichern.isPending}
        onChange={(e) =>
          speichern.mutate({
            al: e.target.value === "" ? null : Number(e.target.value),
            e: grad,
          })
        }
        aria-label={t("kompetenzen.anforderungslevel")}
        className="h-6 w-9 rounded border bg-background px-0.5 text-[11px] tabular-nums
                   focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        <option value="">—</option>
        {[0, 1, 2, 3, 4].map((n) => (
          <option key={n} value={String(n)}>
            {n}
          </option>
        ))}
      </select>
      <input
        type="text"
        inputMode="numeric"
        value={entwurf}
        disabled={speichern.isPending}
        onChange={(e) => setEntwurf(e.target.value)}
        onBlur={gradAbschicken}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
          if (e.key === "Escape") setEntwurf(grad === null ? "" : String(grad));
        }}
        aria-label={t("kompetenzen.erfuellungsgrad")}
        className={`h-6 w-11 rounded border px-1 text-center text-[11px] tabular-nums
                    focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring
                    ${grad === null ? "bg-background" : gradFarbe(grad)}`}
      />
    </span>
  );
}

/** Erläuterungen aus der Excel — was AL und Erfüllungsgrad bedeuten.
 *
 *  Steht in der Excel als Fließtext über der Matrix. Hier zweisprachig aus
 *  den i18n-Dateien, damit die englische Oberfläche nicht auf Deutsch fällt.
 */
function LegendePanel() {
  const { t } = useTranslation();
  const stufen = [1, 2, 3, 4];

  return (
    <section className="mb-6">
      <Klappbar
        titel={t("kompetenzen.erlaeuterungen")}
        icon={<Info className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
        offenStart={false}
      >
        <div className="space-y-4 px-4 py-3 text-sm">
          <div>
            <p className="mb-1 font-medium">{t("kompetenzen.al.title")}</p>
            <p className="mb-2 text-muted-foreground">{t("kompetenzen.al.intro")}</p>
            <ul className="space-y-1">
              {stufen.map((s) => (
                <li key={s} className="flex gap-2">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center
                                   rounded bg-muted text-xs tabular-nums text-muted-foreground">
                    {s}
                  </span>
                  <span>{t(`kompetenzen.al.stufe${s}`)}</span>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="mb-1 font-medium">{t("kompetenzen.eg.title")}</p>
            <p className="text-muted-foreground">{t("kompetenzen.eg.intro")}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {[0, 25, 50, 75, 100].map((g) => (
                <span
                  key={g}
                  className={`rounded px-2 py-0.5 text-xs tabular-nums ${gradFarbe(g)}`}
                >
                  {g} %
                </span>
              ))}
            </div>
          </div>
        </div>
      </Klappbar>
    </section>
  );
}

const feldStil =
  "h-8 rounded-md border bg-background px-2 text-xs " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const knopfStil =
  "inline-flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs " +
  "text-primary-foreground disabled:opacity-50 focus-visible:outline-none " +
  "focus-visible:ring-2 focus-visible:ring-ring";

/** Neue Qualifikation (Zeile). Kategorie als Eingabe mit Vorschlagsliste der
 *  bestehenden Kategorien: das vermeidet Tippfehler-Gruppen neben einer
 *  bestehenden, lässt aber eine neue Kategorie zu (frei eingebbar). */
function ZeileAnlegen({ matrix }: { matrix: Matrix }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [bezeichnung, setBezeichnung] = useState("");
  const [kategorie, setKategorie] = useState("");

  const kategorien = useMemo(
    () =>
      [...new Set(matrix.qualifikationen.map((q) => q.kategorie).filter(Boolean))].sort() as string[],
    [matrix.qualifikationen],
  );

  const anlegen = useMutation({
    mutationFn: () =>
      legeQualifikationAn(matrix.id, {
        bezeichnung,
        kategorie: kategorie || null,
      }),
    onSuccess: () => {
      toast.success(t("kompetenzen.zeileAngelegt"));
      setBezeichnung("");
      qc.invalidateQueries({ queryKey: hrKpiKeys.kompetenzMatrix(matrix.id) });
      qc.invalidateQueries({ queryKey: hrKpiKeys.kompetenzMatrizen() });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium">{t("kompetenzen.neueZeile")}</span>
      <input
        value={bezeichnung}
        onChange={(e) => setBezeichnung(e.target.value)}
        placeholder={t("kompetenzen.qualifikation")}
        className={`${feldStil} w-52`}
      />
      <input
        value={kategorie}
        onChange={(e) => setKategorie(e.target.value)}
        list={`kategorien-${matrix.id}`}
        aria-label={t("kompetenzen.kategorie")}
        placeholder={t("kompetenzen.kategorie")}
        className={`${feldStil} w-44`}
      />
      <datalist id={`kategorien-${matrix.id}`}>
        {kategorien.map((k) => (
          <option key={k} value={k} />
        ))}
      </datalist>
      <button
        type="button"
        disabled={!bezeichnung.trim() || anlegen.isPending}
        onClick={() => anlegen.mutate()}
        className={knopfStil}
      >
        {anlegen.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
        {t("kompetenzen.hinzufuegen")}
      </button>
    </div>
  );
}

/** Eine bestehende Kategorie umbenennen — ändert den Namen auf allen ihren
 *  Zeilen in dieser Matrix. Nur im Bearbeiten-Modus und nicht für die
 *  Platzhaltergruppe „Ohne Kategorie" (deren Zeilen haben keine Kategorie). */
function KategorieUmbenennenFeld({ matrix, alt }: { matrix: Matrix; alt: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [neu, setNeu] = useState(alt);

  const umbenennen = useMutation({
    mutationFn: () => benenneKategorieUm(matrix.id, alt, neu.trim()),
    onSuccess: () => {
      toast.success(t("kompetenzen.kategorieUmbenannt"));
      qc.invalidateQueries({ queryKey: hrKpiKeys.kompetenzMatrix(matrix.id) });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const bereit = neu.trim() !== "" && neu.trim() !== alt;

  return (
    <div className="flex flex-wrap items-center gap-2 px-4 py-2">
      <span className="text-xs font-medium">{t("kompetenzen.kategorieUmbenennen")}</span>
      <input
        value={neu}
        onChange={(e) => setNeu(e.target.value)}
        aria-label={t("kompetenzen.kategorie")}
        className={`${feldStil} w-52`}
      />
      <button
        type="button"
        disabled={!bereit || umbenennen.isPending}
        onClick={() => umbenennen.mutate()}
        className={knopfStil}
      >
        {umbenennen.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
        {t("kompetenzen.speichern")}
      </button>
    </div>
  );
}

/** Neue Person (Spalte).
 *
 *  Regelfall ist die Übernahme aus Personio — abgetippte Namen finden später
 *  keinen Treffer mehr (siehe die Fälle ohne Zuordnung aus dem Erstimport).
 *  Freitext bleibt für Personen möglich, die nicht in Personio stehen.
 */
function SpalteAnlegen({ matrix }: { matrix: Matrix }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [manuell, setManuell] = useState(false);
  const [auswahl, setAuswahl] = useState("");
  const [name, setName] = useState("");

  const { data: verfuegbar } = useQuery({
    queryKey: hrKpiKeys.kompetenzVerfuegbar(matrix.id),
    queryFn: () => fetchVerfuegbarePersonen(matrix.id),
  });

  const anlegen = useMutation({
    mutationFn: () =>
      manuell
        ? legePersonAn(matrix.id, { name })
        : legePersonAn(matrix.id, { name: "", employee_id: Number(auswahl) }),
    onSuccess: (p) => {
      toast.success(t("kompetenzen.personAngelegt2", { name: p.name }));
      setName("");
      setAuswahl("");
      qc.invalidateQueries({ queryKey: hrKpiKeys.kompetenzMatrix(matrix.id) });
      qc.invalidateQueries({ queryKey: hrKpiKeys.kompetenzMatrizen() });
      qc.invalidateQueries({ queryKey: hrKpiKeys.kompetenzVerfuegbar(matrix.id) });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const bereit = manuell ? name.trim() !== "" : auswahl !== "";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium">{t("kompetenzen.neueSpalte")}</span>

      {manuell ? (
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("kompetenzen.person")}
          className={`${feldStil} w-44`}
        />
      ) : (
        <select
          value={auswahl}
          onChange={(e) => setAuswahl(e.target.value)}
          aria-label={t("kompetenzen.person")}
          className={`${feldStil} max-w-[20rem]`}
        >
          <option value="">{t("kompetenzen.personWaehlen")}</option>
          {(verfuegbar ?? []).map((p) => (
            <option key={p.employee_id} value={String(p.employee_id)}>
              {p.name}
              {p.abteilung ? ` · ${p.abteilung}` : ""}
            </option>
          ))}
        </select>
      )}

      <button
        type="button"
        disabled={!bereit || anlegen.isPending}
        onClick={() => anlegen.mutate()}
        className={knopfStil}
      >
        {anlegen.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
        {t("kompetenzen.hinzufuegen")}
      </button>

      <button
        type="button"
        onClick={() => setManuell((v) => !v)}
        className="text-xs text-muted-foreground underline underline-offset-2
                   hover:text-foreground focus-visible:outline-none
                   focus-visible:ring-2 focus-visible:ring-ring"
      >
        {manuell ? t("kompetenzen.ausPersonio") : t("kompetenzen.nichtInPersonio")}
      </button>
    </div>
  );
}

/** Die Matrix selbst — Zeilen nach Kategorie gruppiert, Spalten sind Personen. */
function MatrixTabelle({ matrix }: { matrix: Matrix }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [nurLuecken, setNurLuecken] = useState(false);
  const [bearbeiten, setBearbeiten] = useState(false);

  const aktualisieren = () =>
    qc.invalidateQueries({ queryKey: hrKpiKeys.kompetenzMatrix(matrix.id) });

  const personEntfernen = useMutation({
    mutationFn: (id: number) => entfernePerson(matrix.id, id),
    onSuccess: () => {
      toast.success(t("kompetenzen.personEntfernt"));
      aktualisieren();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const qualEntfernen = useMutation({
    mutationFn: (id: number) => entferneQualifikation(matrix.id, id),
    onSuccess: () => {
      toast.success(t("kompetenzen.zeileEntfernt"));
      aktualisieren();
    },
    onError: (e: Error) => toast.error(e.message),
  });

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

        <button
          type="button"
          onClick={() => setBearbeiten((v) => !v)}
          aria-pressed={bearbeiten}
          className={`ml-auto inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-xs
                      transition-colors focus-visible:outline-none focus-visible:ring-2
                      focus-visible:ring-ring ${
                        bearbeiten
                          ? "bg-primary text-primary-foreground"
                          : "border text-muted-foreground hover:bg-muted"
                      }`}
        >
          <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
          {bearbeiten ? t("kompetenzen.bearbeitenAus") : t("kompetenzen.bearbeitenAn")}
        </button>
      </div>

      {bearbeiten && (
        <div className="mb-3 space-y-3 rounded-lg border border-amber-500/40 bg-amber-500/5 p-3">
          <p className="text-xs text-muted-foreground">{t("kompetenzen.bearbeitenHinweis")}</p>
          <div className="flex flex-wrap gap-4">
            <ZeileAnlegen matrix={matrix} />
            <SpalteAnlegen matrix={matrix} />
          </div>
        </div>
      )}

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
        // Echter Kategoriewert (NULL = Platzhaltergruppe „Ohne Kategorie");
        // die Gruppierung stellt sicher, dass alle Zeilen denselben Wert tragen.
        const rohKategorie = zeilen[0]?.kategorie ?? null;

        return (
          <section key={kategorie} className="mb-4">
            <Klappbar titel={kategorie} anzahl={gezeigt.length}>
              {bearbeiten && rohKategorie !== null && (
                <KategorieUmbenennenFeld matrix={matrix} alt={rohKategorie} />
              )}
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
                          {bearbeiten && (
                            <button
                              type="button"
                              onClick={() => personEntfernen.mutate(p.id)}
                              disabled={personEntfernen.isPending}
                              aria-label={t("kompetenzen.spalteEntfernen", { name: p.name })}
                              title={t("kompetenzen.spalteEntfernen", { name: p.name })}
                              className="ml-1 rounded p-0.5 align-middle text-muted-foreground
                                         transition-colors hover:bg-destructive/10
                                         hover:text-destructive disabled:opacity-50"
                            >
                              <X className="h-3 w-3" aria-hidden="true" />
                            </button>
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
                            {bearbeiten && (
                              <button
                                type="button"
                                onClick={() => qualEntfernen.mutate(q.id)}
                                disabled={qualEntfernen.isPending}
                                aria-label={t("kompetenzen.zeileEntfernen2", {
                                  name: q.bezeichnung,
                                })}
                                title={t("kompetenzen.zeileEntfernen2", {
                                  name: q.bezeichnung,
                                })}
                                className="ml-2 rounded p-0.5 align-middle text-muted-foreground
                                           transition-colors hover:bg-destructive/10
                                           hover:text-destructive disabled:opacity-50"
                              >
                                <X className="h-3 w-3" aria-hidden="true" />
                              </button>
                            )}
                          </td>
                          <td className="px-4 py-1.5 text-right tabular-nums text-muted-foreground">
                            {q.durchschnitt === null ? "—" : `${q.durchschnitt}%`}
                          </td>
                          {matrix.personen.map((p) => {
                            const z = proPerson?.get(p.id);
                            return (
                              <td key={p.id} className="px-2 py-1.5 text-center">
                                {bearbeiten ? (
                                  <ZelleBearbeiten
                                    // Neu montieren, sobald der Server andere Werte
                                    // liefert — sonst bliebe der lokale Entwurf stehen.
                                    key={`${z?.al ?? "-"}:${z?.e ?? "-"}`}
                                    matrixId={matrix.id}
                                    qualifikationId={q.id}
                                    personId={p.id}
                                    level={z?.al ?? null}
                                    grad={z?.e ?? null}
                                  />
                                ) : (
                                  <ZelleAnzeige level={z?.al ?? null} grad={z?.e ?? null} />
                                )}
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

      <LegendePanel />


      {isLoading && (
        <div className="flex h-24 items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" />
        </div>
      )}

      {!isLoading && imBereich.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-20 text-center">
          <Table2 className="h-10 w-10 text-muted-foreground" aria-hidden="true" />
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
