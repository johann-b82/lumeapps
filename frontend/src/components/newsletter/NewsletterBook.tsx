import { useRef } from "react";
import { useTranslation } from "react-i18next";
// @ts-expect-error - react-pageflip liefert keine vollständigen Typen
import HTMLFlipBook from "react-pageflip";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { SeiteInhalt, baueSeiten } from "./NewsletterView";
import { type AusgabeDetail } from "@/lib/newsletterApi";

/** Online-Newsletter als Blätter-Buch (react-pageflip) mit Umblätter-Animation. */
export function NewsletterBook({ ausgabe }: { ausgabe: AusgabeDetail }) {
  const { t } = useTranslation();
  const book = useRef<{ pageFlip: () => { flipNext: () => void; flipPrev: () => void } } | null>(null);

  const seiten = baueSeiten(ausgabe, t).map((desc, i) => (
    <div key={i} className="relative h-full overflow-hidden bg-neutral-200">
      <SeiteInhalt desc={desc} ausgabe={ausgabe} />
    </div>
  ));

  return (
    <div className="flex flex-col items-center gap-3">
      <HTMLFlipBook
        width={520}
        height={520}
        size="stretch"
        minWidth={300}
        maxWidth={620}
        minHeight={300}
        maxHeight={620}
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
