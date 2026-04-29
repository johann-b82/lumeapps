#!/usr/bin/env node
// Phase 47 D-5: enforces the player bundle's import boundary + raw-fetch policy.
//
// Rule 1: frontend/src/player/** MUST NOT import from admin-only paths:
//   ^@/signage/pages/
//   ^@/signage/components/Media
//   ^@/signage/components/Playlist
//   ^@/signage/components/Device
//   ^@/components/admin/
//
// Rule 2: frontend/src/player/** MUST NOT call raw fetch() except in these exempt files:
//   - frontend/src/player/lib/playerApi.ts (the documented apiClient exception per ROADMAP hazard #2)
//   - frontend/src/player/hooks/useSidecarStatus.ts (200ms localhost probe per Pitfall P10)
//   - frontend/src/player/PairingScreen.tsx (anonymous /pair/request + /pair/status — no token to attach)
//
// Rule 3: frontend/src/player/** MUST NOT contain `dark:` Tailwind variants
//   (also covered by check-signage-invariants.mjs after its ROOTS extension in Task 4 — duplicate is OK).

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve, relative, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");
const PLAYER_ROOT = resolve(repoRoot, "src/player");

const FORBIDDEN_IMPORTS = [
  /from\s+["']@\/signage\/pages\//,
  /from\s+["']@\/signage\/components\/Media/,
  /from\s+["']@\/signage\/components\/Playlist/,
  /from\s+["']@\/signage\/components\/Device/,
  /from\s+["']@\/components\/admin\//,
];

const RAW_FETCH = /\bfetch\s*\(/;
const FETCH_EXEMPT = new Set([
  resolve(PLAYER_ROOT, "lib/playerApi.ts"),
  resolve(PLAYER_ROOT, "hooks/useSidecarStatus.ts"),
  resolve(PLAYER_ROOT, "PairingScreen.tsx"),
]);

const DARK_VARIANT = /\bdark:[a-z-]+/;

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    const s = statSync(p);
    if (s.isDirectory()) out.push(...walk(p));
    else if (/\.(ts|tsx)$/.test(p)) out.push(p);
  }
  return out;
}

let violations = 0;
let filesScanned = 0;

for (const f of walk(PLAYER_ROOT)) {
  filesScanned++;
  const src = readFileSync(f, "utf8");
  const isExempt = FETCH_EXEMPT.has(f);
  const lines = src.split("\n");

  lines.forEach((line, i) => {
    // Skip comment-only lines for fetch/dark checks (block comments not handled — keep simple).
    const trimmed = line.trim();
    const isCommentLine = trimmed.startsWith("//") || trimmed.startsWith("*");

    for (const re of FORBIDDEN_IMPORTS) {
      if (re.test(line)) {
        console.error(
          `PLAYER_ISOLATION_VIOLATION (forbidden import): ${relative(repoRoot, f)}:${i + 1}: ${trimmed}`,
        );
        violations++;
      }
    }
    if (!isExempt && !isCommentLine && RAW_FETCH.test(line)) {
      console.error(
        `PLAYER_ISOLATION_VIOLATION (raw fetch in non-exempt file): ${relative(repoRoot, f)}:${i + 1}: ${trimmed}`,
      );
      violations++;
    }
    if (DARK_VARIANT.test(line)) {
      console.error(
        `PLAYER_ISOLATION_VIOLATION (dark: tailwind variant): ${relative(repoRoot, f)}:${i + 1}: ${trimmed}`,
      );
      violations++;
    }
  });
}

console.log(`check-player-isolation: scanned ${filesScanned} files, ${violations} violations`);
process.exit(violations > 0 ? 1 : 0);
