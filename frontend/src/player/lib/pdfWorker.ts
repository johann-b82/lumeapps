// Phase 47 SGN-PLY-10 / D-11: pin pdf.js worker to pdfjs-dist@5.6.205 via Vite ?url import.
// Phase 46-03 PdfPlayer intentionally omits the GlobalWorkerOptions override (per 46-03 SUMMARY);
// Phase 47 owns the pin. main.tsx imports this module BEFORE rendering so all PdfPlayer instances
// inherit the worker URL.
//
// IMPORTANT: configure via react-pdf's re-exported `pdfjs` (not the bare `pdfjs-dist` import).
// react-pdf re-exports the exact module instance its <Document> uses; if Vite ends up handing the
// admin SPA and react-pdf separate instances (lazy chunks, pre-bundling), setting GlobalWorkerOptions
// on the bare import has no effect on the one Document reads. The kiosk happened to work because
// the production build collapses to a single chunk anyway; the dev-mode admin SPA was loading
// "pdf.worker.mjs" relative to the current page and 404'ing into the SPA fallback.

import { pdfjs } from "react-pdf";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

export {};
