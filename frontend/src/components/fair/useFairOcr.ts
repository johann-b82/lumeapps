/**
 * Tesseract.js OCR worker lifecycle for the FAIR editor. The worker is created
 * ONCE and terminated on unmount. Assets are self-hosted under
 * `frontend/public/tesseract/` so OCR works offline behind the auth gate.
 *
 * `recognize` takes a mode:
 *   - "auto" / "text": German + English, single- and multi-line blocks.
 *   - "measure": restricted to digit / dimension characters + single line, so a
 *     number like "20" is never mis-read as a word ("ZU").
 * Returns the text plus Tesseract's confidence so the caller can pick the best
 * orientation. Manual correction always stays available.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { createWorker, PSM } from "tesseract.js";

export type OcrMode = "auto" | "measure" | "text";

const OCR_LANGS = "deu+eng";
const OCR_OPTIONS = {
  workerPath: "/tesseract/worker.min.js",
  corePath: "/tesseract/",
  langPath: "/tesseract/lang",
} as const;

// Digits + the symbols/units that appear in dimension callouts.
const MEASURE_WHITELIST = "0123456789.,+-±ØøRrMmXx°/() ";

type OcrWorker = Awaited<ReturnType<typeof createWorker>>;

export interface OcrResult {
  text: string;
  confidence: number;
}

export function useFairOcr() {
  const workerRef = useRef<OcrWorker | null>(null);
  const lastModeRef = useRef<OcrMode | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const worker = await createWorker(OCR_LANGS, 1, OCR_OPTIONS);
        if (cancelled) {
          await worker.terminate();
          return;
        }
        workerRef.current = worker;
        setReady(true);
      } catch (e) {
        console.error("FAIR OCR init failed", e);
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      const w = workerRef.current;
      workerRef.current = null;
      lastModeRef.current = null;
      if (w) void w.terminate();
    };
  }, []);

  const recognize = useCallback(
    async (canvas: HTMLCanvasElement, mode: OcrMode = "auto"): Promise<OcrResult> => {
      const w = workerRef.current;
      if (!w) return { text: "", confidence: 0 };
      try {
        if (lastModeRef.current !== mode) {
          await w.setParameters(
            mode === "measure"
              ? {
                  tessedit_pageseg_mode: PSM.SINGLE_LINE,
                  tessedit_char_whitelist: MEASURE_WHITELIST,
                }
              : {
                  tessedit_pageseg_mode: PSM.SINGLE_BLOCK,
                  tessedit_char_whitelist: "",
                },
          );
          lastModeRef.current = mode;
        }
        const { data } = await w.recognize(canvas);
        return {
          text: (data.text || "")
            .replace(/[ \t]+/g, " ")
            .replace(/\s*\n\s*/g, " ")
            .trim(),
          confidence: data.confidence ?? 0,
        };
      } catch (e) {
        console.error("FAIR OCR recognize failed", e);
        return { text: "", confidence: 0 };
      }
    },
    [],
  );

  return { ready, failed, recognize };
}
