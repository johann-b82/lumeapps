import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, Check, Loader2, UserPlus, Wrench } from "lucide-react";
import {
  erzeugePlan,
  fetchEintritte,
  fetchPlan,
  fetchKuerzel,
  fetchRollen,
  setzeRolle,
  type Eintritt,
} from "@/lib/onboardingApi";
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
      {data.kuerzel_fehlt && (
        <div className="flex gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{t("onboarding.kuerzelFehlt", { position: data.position ?? "—" })}</span>
        </div>
      )}

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
        </>
      )}
    </div>
  );
}

/** Dropdown in der Zeile: Kürzel für die Position dieses Mitarbeiters wählen.
 *
 *  Die Zuordnung hängt an der POSITION, nicht an der Person — die Auswahl gilt
 *  daher für alle Mitarbeiter mit derselben Positionsbezeichnung. Der Hinweis
 *  über der Tabelle sagt das ausdrücklich.
 */
function KuerzelAuswahl({ eintritt }: { eintritt: Eintritt }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data: kuerzel } = useQuery({
    queryKey: hrKpiKeys.onboardingKuerzel(),
    queryFn: fetchKuerzel,
  });

  const speichern = useMutation({
    mutationFn: (wert: string) =>
      setzeRolle({ position: eintritt.position ?? "", abteilung_kuerzel: wert }),
    onSuccess: (r) => {
      toast.success(t("onboarding.rolleGespeichert", { kuerzel: r.abteilung_kuerzel }));
      qc.invalidateQueries({ queryKey: hrKpiKeys.onboardingEintritte() });
      qc.invalidateQueries({ queryKey: hrKpiKeys.onboardingRollen() });
      qc.invalidateQueries({ queryKey: hrKpiKeys.onboardingKuerzel() });
      qc.invalidateQueries({ queryKey: hrKpiKeys.onboardingPlan(eintritt.employee_id) });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!eintritt.position) {
    return <span className="text-xs text-muted-foreground">{t("onboarding.ohnePosition")}</span>;
  }

  return (
    <select
      value={eintritt.abteilung_kuerzel ?? ""}
      disabled={speichern.isPending}
      onClick={(e) => e.stopPropagation()}
      onChange={(e) => {
        const wert = e.target.value;
        if (wert) speichern.mutate(wert);
      }}
      aria-label={t("onboarding.rollen.kuerzel")}
      className={`h-7 rounded-md border bg-background px-2 text-xs disabled:opacity-50
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
                  ${eintritt.abteilung_kuerzel ? "" : "border-amber-500/60 text-muted-foreground"}`}
    >
      <option value="">{t("onboarding.kuerzelWaehlen")}</option>
      {(kuerzel ?? []).map((k) => (
        <option key={k} value={k}>
          {k}
        </option>
      ))}
    </select>
  );
}

/** Übersicht der bestehenden Zuordnungen (Pflege läuft über die Zeilen-Dropdowns). */
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
                  <Th>{t("onboarding.rollen.kuerzel")}</Th>
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
                      <td className="px-4 py-2">
                        {e.name}
                        {e.kuerzel_fehlt && (
                          <AlertTriangle
                            className="ml-1.5 inline h-3.5 w-3.5 text-amber-500"
                            aria-label={t("onboarding.kuerzelFehltKurz")}
                          />
                        )}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">{e.position ?? "—"}</td>
                      <td className="px-4 py-2 text-muted-foreground">{e.abteilung ?? "—"}</td>
                      <td className="px-4 py-2">
                        <KuerzelAuswahl eintritt={e} />
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
                        <td colSpan={6} className="p-0">
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
