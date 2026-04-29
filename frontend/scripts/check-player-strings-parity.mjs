#!/usr/bin/env node
// Phase 47 — Path B i18n parity gate (Pitfall P9 resolution).
// Asserts that frontend/src/player/lib/strings.ts has the SAME set of keys for 'en' and 'de'.
// Replaces the JSON-locale parity check (scripts/check-i18n-parity.mjs) for the player bundle's
// 5 hard-coded strings.

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");
const STRINGS_FILE = resolve(repoRoot, "src/player/lib/strings.ts");

const src = readFileSync(STRINGS_FILE, "utf8");

// Extract the keys for each locale by scanning the literal STRINGS object.
// Simple regex parse — works because the file is hand-authored with predictable shape.
function extractKeys(localeTag) {
  // Match e.g.   en: { ... }   then capture string keys inside.
  const blockRe = new RegExp(`${localeTag}\\s*:\\s*\\{([\\s\\S]*?)\\}\\s*,?\\s*(?:de|en|\\}\\s*;?)`, "m");
  const m = src.match(blockRe);
  if (!m) {
    console.error(`check-player-strings-parity: could not locate '${localeTag}' block in strings.ts`);
    process.exit(2);
  }
  const body = m[1];
  const keyRe = /["']([a-z_.]+)["']\s*:/g;
  const keys = new Set();
  let km;
  while ((km = keyRe.exec(body))) keys.add(km[1]);
  return keys;
}

const enKeys = extractKeys("en");
const deKeys = extractKeys("de");

const onlyEn = [...enKeys].filter((k) => !deKeys.has(k));
const onlyDe = [...deKeys].filter((k) => !enKeys.has(k));

console.log(`check-player-strings-parity: en=${enKeys.size} keys, de=${deKeys.size} keys`);

if (onlyEn.length > 0) {
  console.error("check-player-strings-parity: keys present in 'en' but missing in 'de':");
  for (const k of onlyEn) console.error(`  - ${k}`);
}
if (onlyDe.length > 0) {
  console.error("check-player-strings-parity: keys present in 'de' but missing in 'en':");
  for (const k of onlyDe) console.error(`  - ${k}`);
}

if (onlyEn.length > 0 || onlyDe.length > 0) {
  console.error("check-player-strings-parity: FAIL");
  process.exit(1);
}
console.log("check-player-strings-parity: PASS");
process.exit(0);
