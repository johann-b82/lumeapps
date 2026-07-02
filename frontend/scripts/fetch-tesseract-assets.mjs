/**
 * Self-host the Tesseract.js runtime under frontend/public/tesseract so OCR
 * works offline behind the auth gate (no CDN dependency at runtime).
 *
 * Copies the worker + wasm core from node_modules and downloads the English
 * traineddata into public/tesseract/lang. Run after `npm install`:
 *     node scripts/fetch-tesseract-assets.mjs
 * Idempotent — existing files are overwritten.
 */
import { cpSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const outDir = join(root, "public", "tesseract");
const langDir = join(outDir, "lang");
const nm = join(root, "node_modules");

mkdirSync(langDir, { recursive: true });

// 1. Worker script.
const workerSrc = join(nm, "tesseract.js", "dist", "worker.min.js");
if (!existsSync(workerSrc)) {
  console.error("tesseract.js worker not found — run `npm install` first.");
  process.exit(1);
}
cpSync(workerSrc, join(outDir, "worker.min.js"));
console.log("copied worker.min.js");

// 2. WASM core (copy every runtime asset — names vary across versions).
const coreDir = join(nm, "tesseract.js-core");
for (const f of readdirSync(coreDir)) {
  if (f.endsWith(".wasm") || f.endsWith(".js")) {
    cpSync(join(coreDir, f), join(outDir, f));
  }
}
console.log("copied tesseract.js-core assets");

// 3. English traineddata (matches tesseract.js default tessdata 4.0.0).
const TESSDATA = "https://tessdata.projectnaptha.com/4.0.0";
for (const lang of ["eng", "deu"]) {
  try {
    const res = await fetch(`${TESSDATA}/${lang}.traineddata.gz`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const buf = Buffer.from(await res.arrayBuffer());
    await writeFile(join(langDir, `${lang}.traineddata.gz`), buf);
    console.log(`downloaded ${lang}.traineddata.gz (${buf.length} bytes)`);
  } catch (e) {
    console.warn(
      `WARN: could not download ${lang}.traineddata.gz (${e.message}). ` +
        "OCR pre-fill will be limited until the file is placed in " +
        "public/tesseract/lang/ — manual value entry still works.",
    );
  }
}
