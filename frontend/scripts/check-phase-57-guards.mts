// Phase 57 CI grep guards — locks in the four eradication invariants
// introduced this phase. Run with:
//   node --experimental-strip-types frontend/scripts/check-phase-57-guards.mts
//
// Exits 0 with "PHASE-57 GUARDS OK" when every invariant holds.
// Exits 1 and prints file:line for each violation.
//
// Invariants enforced:
//   1. window.confirm in frontend/src/    — D-08 eradication.
//   2. Imports of any retired feature-variant dialog name —
//        MediaDeleteDialog, ScheduleDeleteDialog, SensorRemoveDialog,
//        SensorAdminHeader, DeleteConfirmDialog.
//   3. dark: variants in the three new primitives — UI-SPEC §Dark Mode Invariant.
//   4. font-semibold in the three new primitives — typography harmonization gate.
//
// Belt-and-suspenders:
//   5. Invokes check-locale-parity.mts so locale parity is part of the same
//      guard suite (SECTION-02 from Wave 2 plans touching i18n).
//
// Implementation note:
//   No system `rg` is available in the build environment (the dev shell ships
//   only the Claude Code shell function). We therefore implement the same grep
//   semantics in Node — readFileSync + recursive walk — matching the style of
//   the sibling check-signage-invariants.mjs script. Net effect is identical:
//   any match in the scanned set is a CI failure.

import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const repoRoot = resolve(import.meta.dirname, "..", "..");
const SRC_ROOT = resolve(repoRoot, "frontend/src");

const PRIMITIVES = [
  resolve(repoRoot, "frontend/src/components/ui/section-header.tsx"),
  resolve(repoRoot, "frontend/src/components/ui/delete-dialog.tsx"),
  resolve(repoRoot, "frontend/src/components/ui/delete-button.tsx"),
];

const RETIRED_DIALOGS = [
  "MediaDeleteDialog",
  "ScheduleDeleteDialog",
  "SensorRemoveDialog",
  "SensorAdminHeader",
  "DeleteConfirmDialog",
];

// File extensions to scan
const SCAN_EXTS = /\.(ts|tsx|js|jsx|mjs|cjs)$/;

// Exempt: this guard script itself (mentions banned patterns as string literals).
const SELF_PATH = resolve(import.meta.filename);

function walk(dir: string): string[] {
  const out: string[] = [];
  let entries: string[];
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const entry of entries) {
    const p = join(dir, entry);
    const s = statSync(p);
    if (s.isDirectory()) out.push(...walk(p));
    else if (SCAN_EXTS.test(p)) out.push(p);
  }
  return out;
}

interface Violation {
  guard: string;
  file: string;
  line: number;
  text: string;
}

const violations: Violation[] = [];

function scan(
  files: string[],
  guard: string,
  pattern: RegExp,
): void {
  for (const f of files) {
    if (f === SELF_PATH) continue;
    const src = readFileSync(f, "utf8");
    const lines = src.split("\n");
    lines.forEach((line, i) => {
      // Strip trailing single-line comments before matching so that
      // documentation referencing the banned pattern (e.g. "no `dark:`
      // variants") inside the primitives themselves doesn't self-trip.
      const stripped = line.replace(/\/\/.*$/, "");
      if (pattern.test(stripped)) {
        violations.push({
          guard,
          file: f,
          line: i + 1,
          text: line.trim(),
        });
      }
    });
  }
}

// --- Build file lists -----------------------------------------------------

const allSrcFiles = walk(SRC_ROOT);

// --- Guard 1: window.confirm in frontend/src ------------------------------

scan(allSrcFiles, "WINDOW_CONFIRM", /window\.confirm\b/);

// --- Guard 2: retired feature-variant dialog name references --------------

const retiredPattern = new RegExp(`\\b(${RETIRED_DIALOGS.join("|")})\\b`);
scan(allSrcFiles, "RETIRED_DIALOG", retiredPattern);

// --- Guard 3: dark: variants in the three new primitives ------------------

scan(PRIMITIVES, "DARK_VARIANT", /\bdark:/);

// --- Guard 4: font-semibold in the three new primitives -------------------

scan(PRIMITIVES, "FONT_SEMIBOLD", /\bfont-semibold\b/);

// --- Report ---------------------------------------------------------------

if (violations.length > 0) {
  for (const v of violations) {
    const rel = v.file.startsWith(repoRoot)
      ? v.file.slice(repoRoot.length + 1)
      : v.file;
    console.error(`${v.guard}: ${rel}:${v.line}: ${v.text}`);
  }
  console.error(
    `\nFAIL: ${violations.length} Phase 57 guard violation(s).`,
  );
  process.exit(1);
}

// --- Guard 5: locale parity (belt-and-suspenders) -------------------------

const parityScript = resolve(
  repoRoot,
  "frontend/scripts/check-locale-parity.mts",
);

try {
  execFileSync(
    process.execPath,
    ["--experimental-strip-types", parityScript],
    { stdio: "inherit" },
  );
} catch {
  console.error("\nFAIL: locale parity guard failed.");
  process.exit(1);
}

console.log(
  `PHASE-57 GUARDS OK: scanned ${allSrcFiles.length} src file(s) + ${PRIMITIVES.length} primitive(s); locale parity OK.`,
);
