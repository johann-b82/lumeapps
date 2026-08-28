import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  Eye,
  FileText,
  Loader2,
  Upload,
  XCircle,
} from "lucide-react";
import {
  aktualisiereVorgang,
  fetchVorgaenge,
  oeffneVorgangPdf,
  oeffneVorgangScan,
  scanHochladen,
  setzeVorgangStatus,
  type PruefErgebnis,
  type Vorgang,
  type VorgangStatus,
} from "@/lib/einarbeitungApi";
import { hrKpiKeys } from "@/lib/queryKeys";

/** Nächster Lebenszyklus-Schritt (der Laufweg, jetzt im System statt auf Papier). */
const NAECHSTER: Record<VorgangStatus, VorgangStatus | null> = {
  erstellt: "uebergeben",
  uebergeben: "zurueck",
  zurueck: "geprueft",
  geprueft: null,
};

function datum(wert: string | null): string {
  return wert ? new Date(wert).toLocaleDateString("de-DE") : "—";
}

/** Einarbeitungs-Vorgänge: Lebenszyklus + Scan-Upload mit Prüfung. */
export function EinarbeitungVorgaenge() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const dateiRef = useRef<HTMLInputElement>(null);
  const [modal, setModal] = useState<{ dokument: Vorgang; ergebnis: PruefErgebnis } | null>(null);

  const { data: vorgaenge, isLoading } = useQuery({
    queryKey: hrKpiKeys.einarbeitungVorgaenge(),
    queryFn: fetchVorgaenge,
  });

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: hrKpiKeys.einarbeitungVorgaenge() });

  const upload = useMutation({
    mutationFn: (datei: File) => scanHochladen(datei),
    onSuccess: (r) => {
      setModal(r);
      invalidate();
    },
    onError: () => toast.error(t("onboarding.vorgang.scanFehler")),
  });

  const status = useMutation({
    mutationFn: ({ id, ziel }: { id: number; ziel: VorgangStatus }) =>
      setzeVorgangStatus(id, ziel),
    onSuccess: () => invalidate(),
    onError: (e: Error) => toast.error(e.message),
  });

  const pdf = useMutation({
    mutationFn: (id: number) => oeffneVorgangPdf(id),
    // Download = Übergabe → Zeitstempel wird serverseitig gesetzt, Liste neu laden.
    onSuccess: () => invalidate(),
    onError: (e: Error) => toast.error(e.message),
  });

  const scanAnsehen = useMutation({
    mutationFn: (id: number) => oeffneVorgangScan(id),
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <section className="mb-6">
      <div className="mb-1 flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium">{t("onboarding.vorgang.titel")}</h2>
        <button
          type="button"
          onClick={() => dateiRef.current?.click()}
          disabled={upload.isPending}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm
                     text-primary-foreground disabled:opacity-60
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {upload.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Upload className="h-4 w-4" aria-hidden="true" />
          )}
          {t("onboarding.vorgang.scan")}
        </button>
        <input
          ref={dateiRef}
          type="file"
          accept="application/pdf,image/*"
          className="hidden"
          onChange={(e) => {
            const datei = e.target.files?.[0];
            if (datei) upload.mutate(datei);
            e.target.value = "";
          }}
        />
      </div>
      <p className="mb-2 text-xs text-muted-foreground">{t("onboarding.vorgang.hinweis")}</p>

      {isLoading ? (
        <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          {t("onboarding.vorgang.laden")}
        </div>
      ) : !vorgaenge?.length ? (
        <p className="py-4 text-sm text-muted-foreground">{t("onboarding.vorgang.leer")}</p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">{t("onboarding.vorgang.mitarbeiter")}</th>
                <th className="px-3 py-2 font-medium">{t("onboarding.vorgang.status")}</th>
                <th className="px-3 py-2 font-medium">{t("onboarding.vorgang.erstellt")}</th>
                <th className="px-3 py-2 font-medium">{t("onboarding.vorgang.uebergeben")}</th>
                <th className="px-3 py-2 font-medium">{t("onboarding.vorgang.zurueck")}</th>
                <th className="px-3 py-2 font-medium">{t("onboarding.vorgang.geprueft")}</th>
                <th className="px-3 py-2 font-medium">{t("onboarding.vorgang.vollstaendig")}</th>
                <th className="px-3 py-2 font-medium">{t("onboarding.vorgang.aktionen")}</th>
              </tr>
            </thead>
            <tbody>
              {vorgaenge.map((v) => {
                const naechster = NAECHSTER[v.status];
                return (
                  <tr key={v.id} className="border-t">
                    <td className="px-3 py-2">{v.mitarbeiter_name}</td>
                    <td className="px-3 py-2">
                      <span className="rounded-full bg-muted px-2 py-0.5 text-xs">
                        {t(`onboarding.vorgang.statusName.${v.status}`)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs">{datum(v.erstellt_am)}</td>
                    <td className="px-3 py-2 text-xs">{datum(v.uebergeben_am)}</td>
                    <td className="px-3 py-2 text-xs">{datum(v.zurueck_am)}</td>
                    <td className="px-3 py-2 text-xs">{datum(v.geprueft_am)}</td>
                    <td className="px-3 py-2">
                      <VollstaendigBadge wert={v.vollstaendig} />
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          title={t("onboarding.vorgang.pdf")}
                          onClick={() => pdf.mutate(v.id)}
                          className="rounded-md border p-1.5 hover:bg-muted"
                        >
                          <FileText className="h-4 w-4" aria-hidden="true" />
                        </button>
                        {v.hat_scan && (
                          <button
                            type="button"
                            title={t("onboarding.vorgang.scanAnsehen")}
                            onClick={() => scanAnsehen.mutate(v.id)}
                            className="rounded-md border p-1.5 hover:bg-muted"
                          >
                            <Eye className="h-4 w-4" aria-hidden="true" />
                          </button>
                        )}
                        {v.pruef_ergebnis && (
                          <button
                            type="button"
                            title={t("onboarding.vorgang.pruefungOeffnen")}
                            onClick={() =>
                              v.pruef_ergebnis &&
                              setModal({ dokument: v, ergebnis: v.pruef_ergebnis })
                            }
                            className="rounded-md border p-1.5 hover:bg-muted"
                          >
                            <ClipboardCheck className="h-4 w-4" aria-hidden="true" />
                          </button>
                        )}
                        {naechster && (
                          <button
                            type="button"
                            onClick={() => status.mutate({ id: v.id, ziel: naechster })}
                            disabled={status.isPending}
                            className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs
                                       hover:bg-muted disabled:opacity-60"
                          >
                            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                            {t(`onboarding.vorgang.weiterZu.${naechster}`)}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <PruefModal
          daten={modal}
          onClose={() => setModal(null)}
          onGespeichert={invalidate}
        />
      )}
    </section>
  );
}

function VollstaendigBadge({ wert }: { wert: boolean | null }) {
  const { t } = useTranslation();
  if (wert === null) return <span className="text-xs text-muted-foreground">—</span>;
  return wert ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-700
                     dark:bg-green-900/40 dark:text-green-300">
      <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
      {t("onboarding.vorgang.jaVollstaendig")}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-700
                     dark:bg-red-900/40 dark:text-red-300">
      <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
      {t("onboarding.vorgang.nichtVollstaendig")}
    </span>
  );
}

/** Prüf-Fenster nach dem Scan-Upload: erkannte/fehlende Felder + Kommentar/Override. */
function PruefModal({
  daten,
  onClose,
  onGespeichert,
}: {
  daten: { dokument: Vorgang; ergebnis: PruefErgebnis };
  onClose: () => void;
  onGespeichert: () => void;
}) {
  const { t } = useTranslation();
  const { dokument, ergebnis } = daten;
  const [kommentar, setKommentar] = useState(dokument.kommentar ?? "");
  const [bestaetigt, setBestaetigt] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(ergebnis.felder.filter((f) => f.bestaetigt).map((f) => [f.key, true])),
  );

  const istOk = (f: (typeof ergebnis.felder)[number]) => f.erkannt || !!bestaetigt[f.key];
  const offen = ergebnis.felder.filter((f) => !istOk(f));
  const vollstaendig = ergebnis.felder.length > 0 && offen.length === 0;

  const speichern = useMutation({
    mutationFn: () =>
      aktualisiereVorgang(dokument.id, {
        kommentar,
        bestaetigte_felder: Object.keys(bestaetigt).filter((k) => bestaetigt[k]),
      }),
    onSuccess: () => {
      toast.success(t("onboarding.vorgang.gespeichert"));
      onGespeichert();
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const scanOeffnen = useMutation({
    mutationFn: () => oeffneVorgangScan(dokument.id),
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-background p-4 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">
            {t("onboarding.vorgang.pruefTitel", { name: dokument.mitarbeiter_name })}
          </h3>
          <VollstaendigBadge wert={vollstaendig} />
        </div>

        <button
          type="button"
          onClick={() => scanOeffnen.mutate()}
          className="mb-3 inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs hover:bg-muted"
        >
          <Eye className="h-3.5 w-3.5" aria-hidden="true" />
          {t("onboarding.vorgang.scanAnsehen")}
        </button>

        <ul className="mb-3 divide-y rounded-md border text-sm">
          {ergebnis.felder.map((f) => {
            const ok = istOk(f);
            return (
              <li key={f.key} className="flex items-center justify-between gap-2 px-3 py-1.5">
                <span className="flex min-w-0 items-center gap-2">
                  {ok ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600" aria-hidden="true" />
                  ) : (
                    <XCircle className="h-4 w-4 shrink-0 text-red-500" aria-hidden="true" />
                  )}
                  <span className={ok ? "" : "text-muted-foreground"}>{f.label}</span>
                </span>
                {!f.erkannt && (
                  <label className="flex shrink-0 cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={!!bestaetigt[f.key]}
                      onChange={(e) =>
                        setBestaetigt((b) => ({ ...b, [f.key]: e.target.checked }))
                      }
                      className="h-3.5 w-3.5 rounded border-input"
                    />
                    {t("onboarding.vorgang.bestaetigen")}
                  </label>
                )}
              </li>
            );
          })}
        </ul>

        {offen.length > 0 && (
          <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800
                        dark:bg-amber-900/30 dark:text-amber-200">
            {t("onboarding.vorgang.fehlt", { felder: offen.map((f) => f.label).join(", ") })}
          </p>
        )}

        <label className="mb-4 block">
          <span className="mb-1 block text-xs font-medium">{t("onboarding.vorgang.kommentar")}</span>
          <textarea
            value={kommentar}
            onChange={(e) => setKommentar(e.target.value)}
            rows={3}
            className="w-full rounded-md border bg-background px-2 py-1.5 text-sm
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            placeholder={t("onboarding.vorgang.kommentarPlaceholder")}
          />
        </label>

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
          >
            {t("onboarding.vorgang.schliessen")}
          </button>
          <button
            type="button"
            onClick={() => speichern.mutate()}
            disabled={speichern.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm
                       text-primary-foreground disabled:opacity-60"
          >
            {speichern.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
            {t("onboarding.vorgang.speichern")}
          </button>
        </div>
      </div>
    </div>
  );
}
