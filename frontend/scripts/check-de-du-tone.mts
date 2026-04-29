// Du-tone lint — D-03. Scans de.json VALUES for formal-German tokens.
//
// Exits 0 when zero non-allowlisted hits.
// Exits 1 and prints `DU_TONE_HIT: <key-path> | <value>` per offending entry.
//
// Does NOT auto-fix. Per D-03 this is a heuristic lint — humans triage.
//
// Run with:
//   node --experimental-strip-types frontend/scripts/check-de-du-tone.mts

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const repoRoot = resolve(import.meta.dirname, "..", "..");
const dePath = resolve(repoRoot, "frontend/src/locales/de.json");

// Case-sensitive per Pitfall 7 — lowercase `ihr` is legitimate possessive.
const FORMAL = /\b(Sie|Ihnen|Ihre?|Ihrer|Ihres)\b/;

// Allowlist: pre-v1.19 hits (out of D-01 scope). Key path = dotted path from
// the de.json root, using Object.keys recursion. One entry per line; extend
// only with a justification comment referencing the phase/date.
const ALLOWLIST = new Set<string>([
  // v1.13 In-App Documentation — commit 6bc6c275 (2026-04-16); pre-dates
  // v1.19 start (2026-04-21). D-01 puts it out of scope for the sweep.
  // Actual nested path verified 2026-04-22: docs.empty.body (plan's original
  // `empty.body` guess was off by one parent level — `empty` lives under `docs`).
  "docs.empty.body",
  "empty.body",
]);

type JsonVal = string | number | boolean | null | JsonVal[] | { [k: string]: JsonVal };

function walk(node: JsonVal, prefix: string, hits: Array<{ key: string; value: string }>) {
  if (typeof node === "string") {
    if (FORMAL.test(node) && !ALLOWLIST.has(prefix)) {
      hits.push({ key: prefix, value: node });
    }
    return;
  }
  if (node && typeof node === "object" && !Array.isArray(node)) {
    for (const [k, v] of Object.entries(node)) {
      walk(v, prefix ? `${prefix}.${k}` : k, hits);
    }
  }
}

const de = JSON.parse(readFileSync(dePath, "utf8")) as JsonVal;
const hits: Array<{ key: string; value: string }> = [];
walk(de, "", hits);

for (const h of hits) console.log(`DU_TONE_HIT: ${h.key} | ${h.value}`);

if (hits.length === 0) {
  console.log("DU_TONE OK: no non-allowlisted formal-German hits in de.json");
  process.exit(0);
}

console.log(`DU_TONE FAIL: ${hits.length} non-allowlisted hit(s)`);
process.exit(1);
