import { useRef } from "react";
import { useTranslation } from "react-i18next";
// @ts-expect-error - react-pageflip liefert keine vollständigen Typen
import HTMLFlipBook from "react-pageflip";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { AuthImageUrl, BlockInhalt, ordereBloecke } from "./NewsletterView";
import { coverUrl, rueckUrl, type AusgabeDetail } from "@/lib/newsletterApi";

/** Online-Newsletter als Blätter-Buch (react-pageflip) mit Umblätter-Animation. */
export function NewsletterBook({ ausgabe }: { ausgabe: AusgabeDetail }) {
  const { t } = useTranslation();
  const book = useRef<{ pageFlip: () => { flipNext: () => void; flipPrev: () => void } } | null>(null);
  const bloecke = ordereBloecke(ausgabe);
  const titel = ausgabe.titel || `Q${ausgabe.quartal} ${ausgabe.jahr}`;

  const seiten = [
    ausgabe.hat_cover ? (
      <div key="cover" className="relative h-full overflow-hidden bg-neutral-200">
        <AuthImageUrl
          url={coverUrl(ausgabe.id)}
          alt={t("newsletter.titelbild")}
          className="absolute inset-0 block h-full w-full object-cover"
        />
      </div>
    ) : (
      <div
        key="cover"
        className="flex h-full flex-col items-center justify-center bg-gradient-to-br from-sky-600 to-blue-800 p-8 text-center text-white"
      >
        <div className="mb-2 text-sm uppercase tracking-widest opacity-90">
          {t("newsletter.kopf", { quartal: ausgabe.quartal, jahr: ausgabe.jahr })}
        </div>
        <div className="text-3xl font-bold leading-tight">{titel}</div>
        <div className="mt-6 text-xs opacity-80">{t("newsletter.title")}</div>
      </div>
    ),
    ...bloecke.map((b, i) => (
      <div key={i} className="h-full bg-white text-neutral-900">
        <div className="h-full overflow-y-auto p-6">
          <BlockInhalt block={b} rubrikTitel={ausgabe.rubrik_titel} />
        </div>
      </div>
    )),
    ausgabe.hat_rueck ? (
      <div key="back" className="relative h-full overflow-hidden bg-neutral-200">
        <AuthImageUrl
          url={rueckUrl(ausgabe.id)}
          alt={t("newsletter.rueckseitenbild")}
          className="absolute inset-0 block h-full w-full object-cover"
        />
      </div>
    ) : (
      <div
        key="back"
        className="flex h-full items-center justify-center bg-neutral-100 p-8 text-center text-sm text-neutral-500"
      >
        {t("newsletter.buchEnde")}
      </div>
    ),
  ];

  return (
    <div className="flex flex-col items-center gap-3">
      <HTMLFlipBook
        width={440}
        height={440}
        size="stretch"
        minWidth={260}
        maxWidth={480}
        minHeight={260}
        maxHeight={480}
        showCover
        maxShadowOpacity={0.35}
        drawShadow
        flippingTime={700}
        usePortrait={false}
        mobileScrollSupport
        className="nl-book shadow-xl"
        ref={book}
      >
        {seiten}
      </HTMLFlipBook>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => book.current?.pageFlip()?.flipPrev()}
          className="inline-flex h-8 items-center gap-1 rounded-md border border-input px-3 text-xs
                     hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronLeft className="h-3.5 w-3.5" /> {t("newsletter.zurueckblaettern")}
        </button>
        <button
          type="button"
          onClick={() => book.current?.pageFlip()?.flipNext()}
          className="inline-flex h-8 items-center gap-1 rounded-md border border-input px-3 text-xs
                     hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {t("newsletter.weiterblaettern")} <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
