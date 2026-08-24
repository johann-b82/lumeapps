import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { fetchBlob } from "@/lib/download";
import { BelegschaftKpiCharts } from "@/components/dashboard/BelegschaftKpiSection";
import type { BelegschaftKpi } from "@/lib/belegschaftApi";
import {
  NEWSLETTER_RUBRIKEN,
  bildUrl,
  type AusgabeDetail,
  type Eintrag,
  type Rubrik,
} from "@/lib/newsletterApi";

/** Ein Block des Newsletters: eine Rubrik (mit Einträgen) oder der KPI-Block. */
export type NewsletterBlock =
  | { art: "kpi"; data: BelegschaftKpi }
  | { art: "rubrik"; rubrik: Rubrik; eintraege: Eintrag[] };

/** Die Blöcke einer Ausgabe in gespeicherter Reihenfolge; leere Rubriken/KPI
 *  ohne Snapshot fallen raus. */
export function ordereBloecke(a: AusgabeDetail): NewsletterBlock[] {
  const valide = new Set<string>([...NEWSLETTER_RUBRIKEN, "kpi"]);
  const reihenfolge = (a.block_reihenfolge ?? []).filter((k) => valide.has(k));
  for (const k of [...NEWSLETTER_RUBRIKEN, "kpi"]) if (!reihenfolge.includes(k)) reihenfolge.push(k);

  const bloecke: NewsletterBlock[] = [];
  for (const k of reihenfolge) {
    if (k === "kpi") {
      if (a.kpi_snapshot) bloecke.push({ art: "kpi", data: a.kpi_snapshot });
    } else {
      const eintraege = a.eintraege
        .filter((e) => e.rubrik === k)
        .sort((x, y) => x.reihenfolge - y.reihenfolge);
      if (eintraege.length) bloecke.push({ art: "rubrik", rubrik: k as Rubrik, eintraege });
    }
  }
  return bloecke;
}

/** Bild von einem auth-gegateten Endpoint (Bearer nötig) → Blob → Object-URL. */
export function AuthImage({ eintragId, alt }: { eintragId: number; alt: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let aktiv = true;
    let objUrl: string | null = null;
    fetchBlob(bildUrl(eintragId))
      .then((b) => {
        if (!aktiv) return;
        objUrl = URL.createObjectURL(b);
        setUrl(objUrl);
      })
      .catch(() => setUrl(null));
    return () => {
      aktiv = false;
      if (objUrl) URL.revokeObjectURL(objUrl);
    };
  }, [eintragId]);
  if (!url) return null;
  return (
    <img
      src={url}
      alt={alt}
      className="my-2 max-h-72 w-auto rounded-md border border-border object-contain"
    />
  );
}

function EintragBlock({ eintrag }: { eintrag: Eintrag }) {
  return (
    <div className="mb-4 break-inside-avoid">
      <h3 className="mb-1 text-base font-semibold">{eintrag.untertitel}</h3>
      {eintrag.hat_bild && <AuthImage eintragId={eintrag.id} alt={eintrag.untertitel} />}
      {eintrag.inhalt_md.trim() && (
        <div className="prose prose-sm max-w-none dark:prose-invert">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{eintrag.inhalt_md}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}

/** Inhalt eines Blocks (Überschrift + Einträge bzw. KPI-Charts) — geteilt von
 *  Buchseite UND Fließ-Ansicht/PDF. */
export function BlockInhalt({ block }: { block: NewsletterBlock }) {
  const { t } = useTranslation();
  const titel = block.art === "kpi" ? t("newsletter.kpiTitel") : t(`newsletter.rubrik.${block.rubrik}`);
  return (
    <section className="break-inside-avoid">
      <h2 className="mb-3 border-l-4 border-primary pl-2 text-lg font-bold">{titel}</h2>
      {block.art === "kpi" ? (
        <BelegschaftKpiCharts data={block.data} />
      ) : (
        block.eintraege.map((e) => <EintragBlock key={e.id} eintrag={e} />)
      )}
    </section>
  );
}

/** Seitenweise Ansicht — je Block genau eine A4-Seite (Cover, KPI, jede Rubrik,
 *  Rückseite), deckungsgleich zum Buch-Reader. Jede Seite trägt `data-pdf-page`;
 *  der PDF-Export ({@link exportNewsletterPdf}) erfasst sie einzeln. Feste
 *  A4-Maße bei 96 dpi (794 × 1123 px); `minHeight` füllt kurze Seiten voll aus,
 *  längere Blöcke laufen auf eine Folgeseite über. */
export function NewsletterPdfPages({ ausgabe }: { ausgabe: AusgabeDetail }) {
  const { t } = useTranslation();
  const titel = ausgabe.titel || `Q${ausgabe.quartal} ${ausgabe.jahr}`;
  const bloecke = ordereBloecke(ausgabe);
  const seite = { width: 794, minHeight: 1123 };
  return (
    <div className="flex flex-col items-center gap-4">
      <div
        data-pdf-page
        style={seite}
        className="flex flex-col items-center justify-center bg-gradient-to-br from-sky-600
                   to-blue-800 p-16 text-center text-white"
      >
        <div className="mb-3 text-base uppercase tracking-widest opacity-90">
          {t("newsletter.kopf", { quartal: ausgabe.quartal, jahr: ausgabe.jahr })}
        </div>
        <div className="text-5xl font-bold leading-tight">{titel}</div>
        <div className="mt-8 text-sm opacity-80">{t("newsletter.title")}</div>
      </div>

      {bloecke.map((b, i) => (
        <div key={i} data-pdf-page style={seite} className="bg-white p-12 text-neutral-900">
          <BlockInhalt block={b} />
        </div>
      ))}

      <div
        data-pdf-page
        style={seite}
        className="flex items-center justify-center bg-neutral-100 p-16 text-center text-sm
                   text-neutral-500"
      >
        {t("newsletter.buchEnde")}
      </div>
    </div>
  );
}
