import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { Newspaper, FileDown, ChevronLeft, Loader2, PencilLine } from "lucide-react";
import { AdminOnly } from "@/auth/AdminOnly";
import { NewsletterView } from "@/components/newsletter/NewsletterView";
import { exportNewsletterPdf } from "@/lib/newsletterPdf";
import { fetchAusgabe, fetchAusgaben } from "@/lib/newsletterApi";

export function NewsletterPage({ id }: { id?: number }) {
  return id ? <Reader id={id} /> : <Liste />;
}

function Liste() {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();
  const { data } = useQuery({ queryKey: ["newsletter"], queryFn: fetchAusgaben });

  return (
    <div className="mx-auto max-w-3xl px-6 pt-4 pb-10">
      <div className="mb-4 flex items-center gap-2">
        <Newspaper className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="text-lg font-semibold">{t("newsletter.title")}</h1>
        <AdminOnly>
          <button
            type="button"
            onClick={() => setLocation("/newsletter/admin")}
            className="ml-auto inline-flex h-8 items-center gap-2 rounded-md border border-input px-3
                       text-xs hover:bg-muted focus-visible:outline-none focus-visible:ring-2
                       focus-visible:ring-ring"
          >
            <PencilLine className="h-3.5 w-3.5" /> {t("newsletter.redaktion")}
          </button>
        </AdminOnly>
      </div>

      {!data || data.length === 0 ? (
        <div className="rounded-lg border p-6 text-sm text-muted-foreground">
          {t("newsletter.leer")}
        </div>
      ) : (
        <ul className="space-y-2">
          {data.map((a) => (
            <li key={a.id}>
              <button
                type="button"
                onClick={() => setLocation(`/newsletter/${a.id}`)}
                className="flex w-full items-center justify-between rounded-lg border px-4 py-3
                           text-left hover:bg-muted focus-visible:outline-none focus-visible:ring-2
                           focus-visible:ring-ring"
              >
                <span className="font-medium">
                  {a.titel || `Q${a.quartal} ${a.jahr}`}
                </span>
                <span className="text-xs text-muted-foreground">
                  {t("newsletter.kopf", { quartal: a.quartal, jahr: a.jahr })}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Reader({ id }: { id: number }) {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();
  const ref = useRef<HTMLDivElement>(null);
  const [pdfLaeuft, setPdfLaeuft] = useState(false);
  const { data: ausgabe, isError } = useQuery({
    queryKey: ["newsletter", id],
    queryFn: () => fetchAusgabe(id),
  });

  const alsPdf = async () => {
    if (!ref.current || !ausgabe) return;
    setPdfLaeuft(true);
    try {
      await exportNewsletterPdf(
        ref.current,
        `Newsletter_Q${ausgabe.quartal}_${ausgabe.jahr}.pdf`,
      );
    } finally {
      setPdfLaeuft(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-6 pt-4 pb-10">
      <div className="mb-3 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setLocation("/newsletter")}
          className="inline-flex h-8 items-center gap-1 rounded-md border border-input px-2 text-xs
                     hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronLeft className="h-3.5 w-3.5" /> {t("newsletter.zurueck")}
        </button>
        <div className="ml-auto flex items-center gap-2">
          <AdminOnly>
            <button
              type="button"
              onClick={() => setLocation(`/newsletter/admin/${id}`)}
              className="inline-flex h-8 items-center gap-2 rounded-md border border-input px-3 text-xs
                         hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <PencilLine className="h-3.5 w-3.5" /> {t("newsletter.bearbeiten")}
            </button>
          </AdminOnly>
          {ausgabe && (
            <button
              type="button"
              onClick={alsPdf}
              disabled={pdfLaeuft}
              className="inline-flex h-8 items-center gap-2 rounded-md bg-primary px-3 text-xs
                         text-primary-foreground disabled:opacity-50 focus-visible:outline-none
                         focus-visible:ring-2 focus-visible:ring-ring"
            >
              {pdfLaeuft ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileDown className="h-3.5 w-3.5" />}
              {t("newsletter.pdf")}
            </button>
          )}
        </div>
      </div>

      {isError ? (
        <div className="rounded-lg border p-6 text-sm text-muted-foreground">
          {t("newsletter.nichtGefunden")}
        </div>
      ) : ausgabe ? (
        <div ref={ref} className="rounded-lg border">
          <NewsletterView ausgabe={ausgabe} />
        </div>
      ) : (
        <div className="p-6 text-sm text-muted-foreground">…</div>
      )}
    </div>
  );
}
