// Phase 47 SGN-PLY-10 / D-11: pin pdf.js worker to pdfjs-dist@5.6.205 via Vite ?url import.
// Phase 46-03 PdfPlayer intentionally omits the GlobalWorkerOptions override (per 46-03 SUMMARY);
// Phase 47 owns the pin. main.tsx imports this module BEFORE rendering so all PdfPlayer instances
// inherit the worker URL.

import { GlobalWorkerOptions } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = workerUrl;

export {};
