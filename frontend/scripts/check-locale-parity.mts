// Persistent locale parity gate — run with:
//   node --experimental-strip-types frontend/scripts/check-locale-parity.mts
//
// Exits 0 when en.json and de.json have identical key sets.
// Exits 1 and prints a diff report when they diverge.
//
// Does NOT use ESM JSON imports (inconsistent under --experimental-strip-types
// across Node minor versions); uses readFileSync + JSON.parse explicitly.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const repoRoot = resolve(import.meta.dirname, "..", "..");
const enPath = resolve(repoRoot, "frontend/src/locales/en.json");
const dePath = resolve(repoRoot, "frontend/src/locales/de.json");

const en = JSON.parse(readFileSync(enPath, "utf8")) as Record<string, string>;
const de = JSON.parse(readFileSync(dePath, "utf8")) as Record<string, string>;

const enKeys = new Set(Object.keys(en));
const deKeys = new Set(Object.keys(de));

const missingInDe = [...enKeys].filter((k) => !deKeys.has(k)).sort();
const missingInEn = [...deKeys].filter((k) => !enKeys.has(k)).sort();

for (const k of missingInDe) console.log(`MISSING_IN_DE: ${k}`);
for (const k of missingInEn) console.log(`MISSING_IN_EN: ${k}`);

if (missingInDe.length === 0 && missingInEn.length === 0) {
  console.log(`PARITY OK: ${enKeys.size} keys in both en.json and de.json`);
  process.exit(0);
}

console.log(
  `PARITY FAIL: ${missingInDe.length} missing in DE, ${missingInEn.length} missing in EN`,
);
process.exit(1);
