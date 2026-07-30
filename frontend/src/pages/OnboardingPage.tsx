import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Check,
  FileDown,
  ClipboardList,
  FileText,
  Loader2,
  UserPlus,
  Wrench,
  X,
} from "lucide-react";
import {
  erzeugeDokumente,
  erzeugePlan,
  fetchAbteilungen,
  fetchDokumente,
  fetchEintritte,
  fetchPlan,
  fetchRollen,
  ladeDokument,
  ladeOnboardingPaket,
  ladeSchulungsuebersicht,
  setzeAbteilung,
  type Eintritt,
  type OnboardingDokument,
} from "@/lib/onboardingApi";
import {
  entferneInhalt,
  fetchEinarbeitungAbteilungen,
  fetchAnsprechpartner,
  fetchEinarbeitungMatrix,
  ladeEinarbeitungsplan,
  legeInhaltAn,
  type EinarbeitungInhalt,
} from "@/lib/einarbeitungApi";
import { fetchSchulungen } from "@/lib/schulungApi";
import { hrKpiKeys } from "@/lib/queryKeys";
import { Klappbar, Th } from "@/components/hr/Klappbar";

function datum(wert: string | null): string {
  if (!wert) return "—";
  const d = new Date(wert);
  return Number.isNaN(d.getTime()) ? wert : d.toLocaleDateString();
}

/** Schulungsplan einer Person — Soll aus der Matrix, Ist aus dem Bestand. */
function PlanDetail({ eintritt }: { eintritt: Eintritt }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: hrKpiKeys.onboardingPlan(eintritt.employee_id),
    queryFn: () => fetchPlan(eintritt.employee_id),
  });

  const anlegen = useMutation({
    mutationFn: () => erzeugePlan(eintritt.employee_id),
    onSuccess: (plan) => {
      toast.success(t("onboarding.planAngelegt", { count: plan.soll.length }));
      qc.invalidateQueries({ queryKey: hrKpiKeys.onboardingPlan(eintritt.employee_id) });
      qc.invalidateQueries({ queryKey: hrKpiKeys.onboardingEintritte() });
      // Die Schulungssichten zeigen die neuen Zeilen ebenfalls.
      qc.invalidateQueries({ queryKey: hrKpiKeys.schulungMitarbeiter() });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const pdfLaden = useMutation({
    mutationFn: () => ladeSchulungsuebersicht(eintritt.employee_id, eintritt.name),
    onError: (e: Error) => toast.error(e.message),
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-4 py-3 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="space-y-3 px-4 py-3">
      {data.soll.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("onboarding.keinSoll")}</p>
      ) : (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/20">
                <Th>{t("onboarding.schulung")}</Th>
                <Th>{t("onboarding.quelle")}</Th>
                <Th rechts>{t("onboarding.status")}</Th>
              </tr>
            </thead>
            <tbody>
              {data.soll.map((s) => (
                <tr key={s.schulung_id} className="border-b border-border/40 last:border-0">
                  <td className="px-4 py-1.5">
                    <span className="text-muted-foreground">{s.bereich}</span> · {s.name}
                  </td>
                  <td className="px-4 py-1.5">
                    <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {t(`onboarding.ebene.${s.quelle}`)} · {s.abteilung}
                    </span>
                  </td>
                  <td className="px-4 py-1.5 text-right">
                    {s.vorhanden ? (
                      <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-600 dark:text-emerald-400">
                        <Check className="h-3 w-3" aria-hidden="true" />
                        {t("onboarding.angelegt")}
                      </span>
                    ) : (
                      <span className="rounded-md bg-amber-500/15 px-2 py-0.5 text-xs text-amber-600 dark:text-amber-400">
                        {t("onboarding.offen")}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* Außerhalb der Soll-Bedingung: das Formblatt lässt sich auch leer
          ausdrucken und von Hand ausfüllen — und solange die Anforderungsmatrix
          nicht gepflegt ist, ist das Soll bei jedem leer. */}
      <div className="flex flex-wrap items-center gap-2">
        {data.fehlend > 0 && (
          <button
            type="button"
            onClick={() => anlegen.mutate()}
            disabled={anlegen.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm
                       text-primary-foreground disabled:opacity-60
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {anlegen.isPending && (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            )}
            {t("onboarding.planAnlegen", { count: data.fehlend })}
          </button>
        )}

        <button
          type="button"
          onClick={() => pdfLaden.mutate()}
          disabled={pdfLaden.isPending}
          className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm
                     transition-colors hover:bg-muted disabled:opacity-60
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {pdfLaden.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <FileDown className="h-4 w-4" aria-hidden="true" />
          )}
          {t("onboarding.uebersichtPdf")}
        </button>

        <AbteilungsDownload
          eintritt={eintritt}
          label={t("onboarding.einarbeitung.pdf")}
          laden={(a) => ladeEinarbeitungsplan(eintritt.employee_id, eintritt.name, a)}
        />

        <AbteilungsDownload
          eintritt={eintritt}
          primaer
          label={t("onboarding.paket.pdf")}
          laden={(a) => ladeOnboardingPaket(eintritt.employee_id, eintritt.name, a)}
        />
      </div>
    </div>
  );
}

/** Download mit Abteilungsauswahl — geteilt von Einarbeitungsplan und Paket.
 *
 *  Vorbelegt mit der Personio-Abteilung der Person; weitere lassen sich
 *  dazuwählen, für Rollen über mehrere Bereiche (z. B. QS und Produktion).
 */
function AbteilungsDownload({
  eintritt,
  label,
  laden,
  primaer = false,
}: {
  eintritt: Eintritt;
  label: string;
  laden: (abteilungen: string[]) => Promise<void>;
  primaer?: boolean;
}) {
  const { t } = useTranslation();
  const [offen, setOffen] = useState(false);
  const [gewaehlt, setGewaehlt] = useState<string[]>(
    eintritt.abteilung ? [eintritt.abteilung] : [],
  );

  const { data: abteilungen } = useQuery({
    queryKey: hrKpiKeys.einarbeitungAbteilungen(),
    queryFn: fetchEinarbeitungAbteilungen,
    enabled: offen,
  });

  const download = useMutation({
    mutationFn: () => laden(gewaehlt),
    onError: (e: Error) => toast.error(e.message),
  });

  const umschalten = (a: string) =>
    setGewaehlt((v) => (v.includes(a) ? v.filter((x) => x !== a) : [...v, a]));

  const knopfStil = primaer
    ? "bg-primary text-primary-foreground"
    : "border hover:bg-muted";

  if (!offen) {
    return (
      <button
        type="button"
        onClick={() => setOffen(true)}
        className={`inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm
                    transition-colors focus-visible:outline-none focus-visible:ring-2
                    focus-visible:ring-ring ${knopfStil}`}
      >
        <FileDown className="h-4 w-4" aria-hidden="true" />
        {label}
      </button>
    );
  }

  return (
    <div className="flex w-full flex-col gap-2 rounded-md border bg-muted/30 p-3">
      <span className="text-xs font-medium">{t("onboarding.einarbeitung.abteilungen")}</span>
      <div className="flex flex-wrap gap-2">
        {(abteilungen ?? []).map((a) => (
          <label
            key={a}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border
                       bg-background px-2 py-1 text-xs"
          >
            <input
              type="checkbox"
              checked={gewaehlt.includes(a)}
              onChange={() => umschalten(a)}
              className="h-3.5 w-3.5 rounded border-input"
            />
            {a}
          </label>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => download.mutate()}
          disabled={download.isPending || gewaehlt.length === 0}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm
                     text-primary-foreground disabled:opacity-60
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {download.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <FileDown className="h-4 w-4" aria-hidden="true" />
          )}
          {t("onboarding.einarbeitung.erzeugen")}
        </button>
        <button
          type="button"
          onClick={() => setOffen(false)}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          {t("onboarding.einarbeitung.abbrechen")}
        </button>
      </div>
    </div>
  );
}

/** Einarbeitungsmatrix: je Abteilung die Einarbeitungsinhalte + Ansprechpartner.
 *
 *  App-gepflegt. Aus diesen Zeilen setzt sich der Einarbeitungsbogen einer
 *  Person zusammen (über ihre Abteilung).
 */
function EinarbeitungMatrixPanel() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [abteilung, setAbteilung] = useState("");
  const [inhalt, setInhalt] = useState("");
  const [partner, setPartner] = useState("");

  const { data } = useQuery({
    queryKey: hrKpiKeys.einarbeitungMatrix(),
    queryFn: fetchEinarbeitungMatrix,
  });
  const { data: abteilungen } = useQuery({
    queryKey: hrKpiKeys.einarbeitungAbteilungen(),
    queryFn: fetchEinarbeitungAbteilungen,
  });
  const { data: partnerVorschlaege } = useQuery({
    queryKey: hrKpiKeys.einarbeitungAnsprechpartner(),
    queryFn: fetchAnsprechpartner,
  });
  // Schulungskatalog als Inhalts-Vorschläge (die Basis der Anforderungsmatrix).
  const { data: katalog } = useQuery({
    queryKey: hrKpiKeys.schulungen(),
    queryFn: fetchSchulungen,
  });

  const auffrischen = () => {
    qc.invalidateQueries({ queryKey: hrKpiKeys.einarbeitungMatrix() });
    qc.invalidateQueries({ queryKey: hrKpiKeys.einarbeitungAbteilungen() });
  };

  const anlegen = useMutation({
    mutationFn: () =>
      legeInhaltAn({ abteilung, inhalt, ansprechpartner: partner || null }),
    onSuccess: () => {
      toast.success(t("onboarding.einarbeitung.inhaltAngelegt"));
      setInhalt("");
      setPartner("");
      auffrischen();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const entfernen = useMutation({
    mutationFn: entferneInhalt,
    onSuccess: () => {
      toast.success(t("onboarding.einarbeitung.inhaltEntfernt"));
      auffrischen();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Nach Abteilung gruppieren, Reihenfolge kommt schon sortiert vom Server.
  const gruppen = new Map<string, EinarbeitungInhalt[]>();
  for (const z of data ?? []) {
    const liste = gruppen.get(z.abteilung) ?? [];
    liste.push(z);
    gruppen.set(z.abteilung, liste);
  }

  // Vorschläge fürs Inhaltsfeld: die Schulungen aus dem Katalog (woraus die
  // Anforderungsmatrix besteht) plus die bereits erfassten Einarbeitungsinhalte.
  // So ist die Liste von Anfang an nützlich und derselbe Inhalt lässt sich über
  // Abteilungen hinweg wiederverwenden, ohne ihn abzutippen.
  const inhaltVorschlaege = [
    ...new Set([
      ...(katalog ?? []).map((s) => s.name.trim()),
      ...(data ?? []).map((z) => z.inhalt.trim()),
    ].filter(Boolean)),
  ].sort();

  const feldStil =
    "h-8 rounded-md border bg-background px-2 text-xs " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

  return (
    <section className="mb-6">
      <Klappbar
        titel={t("onboarding.einarbeitung.matrixTitle")}
        anzahl={data?.length ?? 0}
        icon={<ClipboardList className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
        offenStart={false}
      >
        <div className="space-y-4 px-4 py-3">
          <p className="text-xs text-muted-foreground">
            {t("onboarding.einarbeitung.matrixHinweis")}
          </p>

          {/* Neue Zeile anlegen */}
          <div className="flex flex-wrap items-end gap-2">
            <input
              list="einarb-abteilungen"
              value={abteilung}
              onChange={(e) => setAbteilung(e.target.value)}
              placeholder={t("onboarding.einarbeitung.abteilung")}
              className={`${feldStil} w-40`}
            />
            <datalist id="einarb-abteilungen">
              {(abteilungen ?? []).map((a) => (
                <option key={a} value={a} />
              ))}
            </datalist>
            <input
              list="einarb-ansprechpartner"
              value={partner}
              onChange={(e) => setPartner(e.target.value)}
              placeholder={t("onboarding.einarbeitung.ansprechpartner")}
              className={`${feldStil} w-44`}
            />
            <datalist id="einarb-ansprechpartner">
              {(partnerVorschlaege ?? []).map((n) => (
                <option key={n} value={n} />
              ))}
            </datalist>
            <input
              list="einarb-inhalte"
              value={inhalt}
              onChange={(e) => setInhalt(e.target.value)}
              placeholder={t("onboarding.einarbeitung.inhalt")}
              className={`${feldStil} min-w-[16rem] flex-1`}
            />
            <datalist id="einarb-inhalte">
              {inhaltVorschlaege.map((i) => (
                <option key={i} value={i} />
              ))}
            </datalist>
            <button
              type="button"
              onClick={() => anlegen.mutate()}
              disabled={!abteilung.trim() || !inhalt.trim() || anlegen.isPending}
              className="inline-flex h-8 items-center gap-2 rounded-md bg-primary px-3 text-xs
                         text-primary-foreground disabled:opacity-50
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {anlegen.isPending && (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              )}
              {t("onboarding.einarbeitung.hinzufuegen")}
            </button>
          </div>

          {gruppen.size === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("onboarding.einarbeitung.matrixLeer")}
            </p>
          ) : (
            [...gruppen.entries()].map(([abt, zeilen]) => (
              <div key={abt}>
                <h3 className="mb-1 text-xs font-semibold text-muted-foreground">{abt}</h3>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/20">
                      <Th>{t("onboarding.einarbeitung.ansprechpartner")}</Th>
                      <Th>{t("onboarding.einarbeitung.inhalt")}</Th>
                      <Th rechts>{""}</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {zeilen.map((z) => (
                      <tr key={z.id} className="border-b border-border/40 last:border-0">
                        <td className="px-4 py-1.5 text-muted-foreground">
                          {z.ansprechpartner ?? "—"}
                        </td>
                        <td className="px-4 py-1.5">{z.inhalt}</td>
                        <td className="px-4 py-1.5 text-right">
                          <button
                            type="button"
                            onClick={() => entfernen.mutate(z.id)}
                            disabled={entfernen.isPending}
                            aria-label={t("onboarding.einarbeitung.zeileEntfernen")}
                            title={t("onboarding.einarbeitung.zeileEntfernen")}
                            className="rounded-md p-1 text-muted-foreground transition-colors
                                       hover:bg-destructive/10 hover:text-destructive
                                       disabled:opacity-50 focus-visible:outline-none
                                       focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            <X className="h-3.5 w-3.5" aria-hidden="true" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))
          )}
        </div>
      </Klappbar>
    </section>
  );
}

/** Automatisch erzeugte Schulungsübersichten.
 *
 *  Der Lauf hängt am Personio-Abgleich; der Knopf hier ist für den Fall, dass
 *  gerade die Anforderungsmatrix gepflegt wurde und man nicht bis zum nächsten
 *  Abgleich warten will.
 */
function DokumentePanel() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: hrKpiKeys.onboardingDokumente(),
    queryFn: fetchDokumente,
  });

  const erzeugen = useMutation({
    mutationFn: erzeugeDokumente,
    onSuccess: (r) => {
      toast.success(
        t("onboarding.dokumente.lauf", {
          erzeugt: r.erzeugt,
          aktualisiert: r.aktualisiert,
        }),
      );
      if (r.uebersprungen_leer > 0) {
        // Kein Fehler, aber der häufigste Grund für "es passiert nichts".
        toast.warning(
          t("onboarding.dokumente.ohneSoll", { count: r.uebersprungen_leer }),
        );
      }
      qc.invalidateQueries({ queryKey: hrKpiKeys.onboardingDokumente() });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const laden = useMutation({
    mutationFn: (d: OnboardingDokument) => ladeDokument(d.employee_id, d.dateiname),
    onError: (e: Error) => toast.error(e.message),
  });

  const veraltet = (data ?? []).filter((d) => d.veraltet).length;

  return (
    <section className="mb-6">
      <Klappbar
        titel={t("onboarding.dokumente.title")}
        anzahl={data?.length ?? 0}
        icon={<FileText className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
        offenStart={false}
      >
        <div className="space-y-3 px-4 py-3">
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-xs text-muted-foreground">
              {t("onboarding.dokumente.hinweis")}
            </p>
            <button
              type="button"
              onClick={() => erzeugen.mutate()}
              disabled={erzeugen.isPending}
              className="ml-auto inline-flex items-center gap-2 rounded-md border px-3 py-1.5
                         text-xs transition-colors hover:bg-muted disabled:opacity-60
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {erzeugen.isPending && (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              )}
              {t("onboarding.dokumente.jetztErzeugen")}
            </button>
          </div>

          {veraltet > 0 && (
            <p className="rounded-md border border-amber-500/40 bg-amber-500/10 p-2 text-xs">
              {t("onboarding.dokumente.veraltetHinweis", { count: veraltet })}
            </p>
          )}

          {(data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("onboarding.dokumente.leer")}
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/20">
                  <Th>{t("onboarding.dokumente.datei")}</Th>
                  <Th rechts>{t("onboarding.schulung")}</Th>
                  <Th rechts>{t("onboarding.dokumente.erzeugtAm")}</Th>
                  <Th rechts>{""}</Th>
                </tr>
              </thead>
              <tbody>
                {(data ?? []).map((d) => (
                  <tr
                    key={d.employee_id}
                    className="border-b border-border/40 last:border-0"
                  >
                    <td className="px-4 py-1.5">
                      {d.dateiname}
                      {d.veraltet && (
                        <span className="ml-2 rounded-md bg-amber-500/15 px-2 py-0.5 text-xs text-amber-600 dark:text-amber-400">
                          {t("onboarding.dokumente.veraltet")}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-1.5 text-right tabular-nums">{d.schulungen}</td>
                    <td className="px-4 py-1.5 text-right whitespace-nowrap tabular-nums text-muted-foreground">
                      {datum(d.erzeugt_am)}
                    </td>
                    <td className="px-4 py-1.5 text-right">
                      <button
                        type="button"
                        onClick={() => laden.mutate(d)}
                        aria-label={t("onboarding.dokumente.herunterladen")}
                        title={t("onboarding.dokumente.herunterladen")}
                        className="rounded-md p-1 text-muted-foreground transition-colors
                                   hover:bg-muted hover:text-foreground
                                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <FileDown className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Klappbar>
    </section>
  );
}

/** Übersicht der bestehenden Positions→Kürzel-Zuordnungen (nur Anzeige). */
function RollenPanel() {
  const { t } = useTranslation();
  const { data } = useQuery({
    queryKey: hrKpiKeys.onboardingRollen(),
    queryFn: fetchRollen,
  });
  if (!data || data.length === 0) return null;

  return (
    <section className="mb-6">
      <Klappbar
        titel={t("onboarding.rollen.title")}
        anzahl={data.length}
        icon={<Wrench className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
        offenStart={false}
      >
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/20">
              <Th>{t("onboarding.rollen.position")}</Th>
              <Th>{t("onboarding.rollen.kuerzel")}</Th>
            </tr>
          </thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.id} className="border-b border-border/40 last:border-0">
                <td className="px-4 py-1.5">{r.position}</td>
                <td className="px-4 py-1.5">
                  <span className="rounded-md bg-muted px-2 py-0.5 text-xs">
                    {r.abteilung_kuerzel}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Klappbar>
    </section>
  );
}

/** Dropdown in der Zeile: Abteilung dieses Mitarbeiters wählen/ändern.
 *
 *  Personio ist read-only — die Auswahl wird als app-seitiger Override
 *  gespeichert und ersetzt den Personio-Wert für die Plan-Berechnung. Leere
 *  Auswahl entfernt den Override (Personio-Abteilung gilt wieder). */
function AbteilungAuswahl({ eintritt }: { eintritt: Eintritt }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data: abteilungen } = useQuery({
    queryKey: hrKpiKeys.onboardingAbteilungen(),
    queryFn: fetchAbteilungen,
  });

  const speichern = useMutation({
    mutationFn: (wert: string) => setzeAbteilung(eintritt.employee_id, wert),
    onSuccess: () => {
      toast.success(t("onboarding.abteilungAktualisiert"));
      qc.invalidateQueries({ queryKey: hrKpiKeys.onboardingEintritte() });
      qc.invalidateQueries({ queryKey: hrKpiKeys.onboardingPlan(eintritt.employee_id) });
      qc.invalidateQueries({ queryKey: hrKpiKeys.onboardingAbteilungen() });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <select
      value={eintritt.abteilung ?? ""}
      disabled={speichern.isPending}
      onClick={(e) => e.stopPropagation()}
      onChange={(e) => speichern.mutate(e.target.value)}
      aria-label={t("onboarding.eintritte.abteilung")}
      className={`h-7 rounded-md border bg-background px-2 text-xs disabled:opacity-50
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
                  ${eintritt.abteilung ? "" : "border-amber-500/60 text-muted-foreground"}`}
    >
      <option value="">{t("onboarding.abteilungWaehlen")}</option>
      {(abteilungen ?? []).map((a) => (
        <option key={a} value={a}>
          {a}
        </option>
      ))}
    </select>
  );
}

export function OnboardingPage() {
  const { t } = useTranslation();
  const [offenFuer, setOffenFuer] = useState<number | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: hrKpiKeys.onboardingEintritte(),
    queryFn: fetchEintritte,
  });

  return (
    <div className="mx-auto max-w-7xl px-6 pt-4 pb-8">
      <h1 className="mb-1 flex items-center gap-2 text-lg font-semibold">
        <UserPlus className="h-5 w-5" aria-hidden="true" />
        {t("hr.onboarding.title")}
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">{t("onboarding.untertitel")}</p>

      <EinarbeitungMatrixPanel />
      <DokumentePanel />
      <RollenPanel />

      <section>
        <h2 className="mb-1 text-sm font-medium">{t("onboarding.eintritte.title")}</h2>
        <p className="mb-3 text-xs text-muted-foreground">
          {t("onboarding.rollen.hinweis")}
        </p>

        {isLoading && (
          <div className="flex h-32 items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" />
          </div>
        )}

        {data && data.length === 0 && (
          <p className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
            {t("onboarding.eintritte.leer")}
          </p>
        )}

        {data && data.length > 0 && (
          <div className="overflow-x-auto rounded-xl border bg-card shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/30">
                  <Th>{t("onboarding.eintritte.name")}</Th>
                  <Th>{t("onboarding.eintritte.position")}</Th>
                  <Th>{t("onboarding.eintritte.abteilung")}</Th>
                  <Th>{t("onboarding.eintritte.eintritt")}</Th>
                  <Th rechts>{t("onboarding.eintritte.plan")}</Th>
                </tr>
              </thead>
              <tbody>
                {data.map((e) => {
                  const offen = offenFuer === e.employee_id;
                  return [
                    <tr
                      key={e.employee_id}
                      onClick={() => setOffenFuer(offen ? null : e.employee_id)}
                      className="cursor-pointer border-b border-border/50 transition-colors hover:bg-muted/40"
                    >
                      <td className="px-4 py-2">{e.name}</td>
                      <td className="px-4 py-2 text-muted-foreground">{e.position ?? "—"}</td>
                      <td className="px-4 py-2">
                        <AbteilungAuswahl eintritt={e} />
                      </td>
                      <td className="px-4 py-2 whitespace-nowrap tabular-nums">
                        {datum(e.hire_date)}
                      </td>
                      <td className="px-4 py-2 text-right whitespace-nowrap">
                        {e.soll_gesamt === 0 ? (
                          <span className="text-xs text-muted-foreground">
                            {t("onboarding.keineRegel")}
                          </span>
                        ) : e.fehlend === 0 ? (
                          <span className="rounded-md bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-600 dark:text-emerald-400">
                            {t("onboarding.vollstaendig", { count: e.soll_gesamt })}
                          </span>
                        ) : (
                          <span className="rounded-md bg-amber-500/15 px-2 py-0.5 text-xs text-amber-600 dark:text-amber-400">
                            {t("onboarding.offenVon", {
                              fehlend: e.fehlend,
                              gesamt: e.soll_gesamt,
                            })}
                          </span>
                        )}
                      </td>
                    </tr>,
                    offen ? (
                      <tr key={`${e.employee_id}-detail`} className="border-b bg-muted/10">
                        <td colSpan={5} className="p-0">
                          <PlanDetail eintritt={e} />
                        </td>
                      </tr>
                    ) : null,
                  ];
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
