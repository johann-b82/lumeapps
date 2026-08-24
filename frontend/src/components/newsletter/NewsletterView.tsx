import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { fetchBlob } from "@/lib/download";
import { BelegschaftKpiCharts } from "@/components/dashboard/BelegschaftKpiSection";
import {
  NEWSLETTER_RUBRIKEN,
  bildUrl,
  type AusgabeDetail,
  type Eintrag,
} from "@/lib/newsletterApi";

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

/** Rendert eine ganze Ausgabe (sechs Rubriken) — genutzt für Ansicht UND PDF-Export. */
export function NewsletterView({ ausgabe }: { ausgabe: AusgabeDetail }) {
  const { t } = useTranslation();
  const titel = ausgabe.titel || `Q${ausgabe.quartal} ${ausgabe.jahr}`;
  return (
    <article className="mx-auto max-w-3xl bg-background p-6">
      <header className="mb-6 border-b pb-4">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">
          {t("newsletter.kopf", { quartal: ausgabe.quartal, jahr: ausgabe.jahr })}
        </div>
        <h1 className="text-2xl font-bold">{titel}</h1>
      </header>

      {ausgabe.kpi_snapshot && (
        <section className="mb-6 break-inside-avoid">
          <h2 className="mb-3 border-l-4 border-primary pl-2 text-lg font-bold">
            {t("newsletter.kpiTitel")}
          </h2>
          <BelegschaftKpiCharts data={ausgabe.kpi_snapshot} />
        </section>
      )}

      {NEWSLETTER_RUBRIKEN.map((rubrik) => {
        const eintraege = ausgabe.eintraege
          .filter((e) => e.rubrik === rubrik)
          .sort((a, b) => a.reihenfolge - b.reihenfolge);
        if (eintraege.length === 0) return null;
        return (
          <section key={rubrik} className="mb-6 break-inside-avoid">
            <h2 className="mb-3 border-l-4 border-primary pl-2 text-lg font-bold">
              {t(`newsletter.rubrik.${rubrik}`)}
            </h2>
            {eintraege.map((e) => (
              <EintragBlock key={e.id} eintrag={e} />
            ))}
          </section>
        );
      })}
    </article>
  );
}
