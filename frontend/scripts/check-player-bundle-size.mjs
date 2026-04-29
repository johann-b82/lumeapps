#!/usr/bin/env node
// Phase 47 SGN-PLY-01: assert dist/player/assets/*.js gzipped total under cap.
// Deterministic via Node zlib (Pitfall P11) — no system gzip dependency.
//
// Phase 48 Plan 48-05 amendment (2026-04-20): LIMIT raised from 200_000 → 210_000
// to accommodate the Tailwind CSS layer added by Phase 47 DEFECT-1.
// Phase 50 SGN-POL-05 (2026-04-21): reset to 200_000 after dynamic-importing
// PdfPlayer + react-pdf in PlayerRenderer.tsx. Any future raise is an
// orchestrator decision — do NOT grow silently.
//
// Phase 50 Plan 50-01 measurement fix (2026-04-21): the SGN-POL-05 goal is
// that the INITIAL (eager) player entry ships <200 KB gz; lazy-loaded chunks
// (PdfPlayer-*.js, pdf-*.js) are fetched on-demand only when a `kind='pdf'`
// item actually renders, so they must NOT count against the entry cap. We
// exclude them here by filename prefix. Any new lazy chunks introduced in
// future plans MUST be added to LAZY_PREFIXES below.
//
// Run AFTER `npm run build` (or `npm run build:player`).

import { readFileSync, readdirSync, existsSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");
const ASSETS = resolve(repoRoot, "dist/player/assets");
const LIMIT = 200_000;

// Lazy-loaded chunks (React.lazy + dynamic import) — excluded from entry cap.
// Files whose basename starts with any of these prefixes are NOT counted.
const LAZY_PREFIXES = ["PdfPlayer-", "pdf-"];

if (!existsSync(ASSETS)) {
  console.error(`check-player-bundle-size: ${ASSETS} does not exist — run \`npm run build\` first`);
  process.exit(2);
}

const allFiles = readdirSync(ASSETS).filter((f) => f.endsWith(".js"));
if (allFiles.length === 0) {
  console.error(`check-player-bundle-size: no .js files in ${ASSETS}`);
  process.exit(2);
}

const isLazy = (f) => LAZY_PREFIXES.some((p) => f.startsWith(p));
const entryFiles = allFiles.filter((f) => !isLazy(f));
const lazyFiles = allFiles.filter(isLazy);

let total = 0;
const breakdown = [];
for (const f of entryFiles) {
  const buf = readFileSync(join(ASSETS, f));
  const gz = gzipSync(buf, { level: 9 }).length;
  breakdown.push({ file: f, raw: buf.length, gz, lazy: false });
  total += gz;
}
const lazyBreakdown = [];
for (const f of lazyFiles) {
  const buf = readFileSync(join(ASSETS, f));
  const gz = gzipSync(buf, { level: 9 }).length;
  lazyBreakdown.push({ file: f, raw: buf.length, gz, lazy: true });
}

breakdown.sort((a, b) => b.gz - a.gz);
lazyBreakdown.sort((a, b) => b.gz - a.gz);
console.log("check-player-bundle-size: ENTRY per-file (gzipped, sorted desc):");
for (const { file, raw, gz } of breakdown) {
  const rawKb = (raw / 1024).toFixed(1);
  const gzKb = (gz / 1024).toFixed(1);
  console.log(`  ${gzKb.padStart(8)} KB gz   (${rawKb.padStart(8)} KB raw)   ${file}`);
}
if (lazyBreakdown.length > 0) {
  console.log("check-player-bundle-size: LAZY chunks (NOT counted against entry cap):");
  for (const { file, raw, gz } of lazyBreakdown) {
    const rawKb = (raw / 1024).toFixed(1);
    const gzKb = (gz / 1024).toFixed(1);
    console.log(`  ${gzKb.padStart(8)} KB gz   (${rawKb.padStart(8)} KB raw)   ${file}`);
  }
}
const totalKb = (total / 1024).toFixed(1);
const limitKb = (LIMIT / 1024).toFixed(1);
const pct = ((total / LIMIT) * 100).toFixed(1);
console.log(`check-player-bundle-size: TOTAL ${totalKb} KB gz / ${limitKb} KB limit (${pct}%)`);

if (total > LIMIT) {
  console.error(`check-player-bundle-size: FAIL — ${total} bytes > ${LIMIT} byte limit`);
  process.exit(1);
}
console.log("check-player-bundle-size: PASS");
process.exit(0);
