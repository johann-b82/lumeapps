// Phase 59 CI grep guards — A11Y-02 + A11Y-03 lock-in.
//
// Exits 0 with "PHASE-59 GUARDS OK" when every invariant holds.
// Exits 1 and prints file:line per violation.
//
// Invariants enforced:
//   1. No hex/rgb/hsl/oklch/oklab color literal inside className= or className={`...`}
//      or inside inline style={{...}} in .tsx/.jsx. Allowlist:
//        - frontend/src/components/settings/ColorPicker.tsx (D-05 user-chosen swatch)
//   2. <Button ... size="icon" | "icon-xs" | "icon-sm" | "icon-lg"> that lacks an
//      aria-label attribute on the SAME element. (Pitfall 8)
//
// Scope: frontend/src recursively, extensions .ts|.tsx|.js|.jsx|.mjs|.cjs.
// Scope EXPLICITLY EXCLUDES .css files — Pitfall 4. The hljs hex literals in
// index.css are syntax-highlighting theme colors, not component style.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const repoRoot = resolve(import.meta.dirname, "..", "..");
const SRC_ROOT = resolve(repoRoot, "frontend/src");
const SCAN_EXTS = /\.(ts|tsx|js|jsx|mjs|cjs)$/;
const SELF_PATH = resolve(import.meta.filename);

const COLOR_LITERAL_ALLOWLIST = new Set<string>([
  resolve(repoRoot, "frontend/src/components/settings/ColorPicker.tsx"),
]);

// Hex 3-8 digits, or css color functions. Named colors (red/blue/…) would
// produce too many false-positives in prose so we deliberately skip them —
// D-05's spirit is about static surface colors, and hex/rgb/hsl captures all
// the real risks.
const HEX = /#[0-9a-fA-F]{3,8}\b/;
const COLOR_FN = /\b(rgb|rgba|hsl|hsla|oklch|oklab)\s*\(/;

// Only flag when the literal sits inside a className or style context. We
// approximate by requiring the line also contains `className` or `style=` or
// is inside a string assigned to one of those (catches both inline
// `className="…#fff…"` and `style={{ color: "#fff" }}`).
const CONTEXT_HINT = /className\s*=|style\s*=\s*\{\{/;

// Button icon-size without aria-label on the same tag.
// We locate `<Button` openings and scan forward to the matching `>` respecting
// JSX-expression brace nesting and quoted strings (so inline arrow fns like
// `onClick={(e) => …}` don't prematurely terminate the tag). Only tags whose
// opening tag text contains size="icon(-xs|-sm|-lg)?" are flagged when
// aria-label is absent from that same opening tag.
const BUTTON_OPEN = /<Button\b/g;
const ICON_SIZE = /\bsize\s*=\s*\{?\s*["'](?:icon(?:-xs|-sm|-lg)?)["']\s*\}?/;

function extractOpeningTag(src: string, start: number): { tag: string; end: number } | null {
  // start points at '<' of <Button. Walk forward tracking JSX expression braces
  // and string/template literals until we hit the terminating `>` (or `/>`).
  let i = start;
  let braceDepth = 0;
  // We are inside an opening tag from the beginning.
  // Handle: "..." '...' `...` {expr with nested {}}.
  const len = src.length;
  // Skip the '<' char, find end of tag name to start scanning attributes.
  i += 1;
  while (i < len) {
    const ch = src[i];
    if (braceDepth === 0) {
      if (ch === '"' || ch === "'" || ch === '`') {
        const quote = ch;
        i += 1;
        while (i < len && src[i] !== quote) {
          if (src[i] === '\\') i += 2;
          else i += 1;
        }
        i += 1; // skip closing quote
        continue;
      }
      if (ch === '{') {
        braceDepth += 1;
        i += 1;
        continue;
      }
      if (ch === '>') {
        return { tag: src.slice(start, i + 1), end: i };
      }
      i += 1;
    } else {
      if (ch === '{') braceDepth += 1;
      else if (ch === '}') braceDepth -= 1;
      else if (ch === '"' || ch === "'" || ch === '`') {
        const quote = ch;
        i += 1;
        while (i < len && src[i] !== quote) {
          if (src[i] === '\\') i += 2;
          else i += 1;
        }
      }
      i += 1;
    }
  }
  return null;
}

interface Violation { guard: string; file: string; line: number; text: string; }
const violations: Violation[] = [];

function walk(dir: string): string[] {
  const out: string[] = [];
  let entries: string[];
  try { entries = readdirSync(dir); } catch { return out; }
  for (const entry of entries) {
    const p = join(dir, entry);
    const s = statSync(p);
    if (s.isDirectory()) out.push(...walk(p));
    else if (SCAN_EXTS.test(p)) out.push(p);
  }
  return out;
}

function stripLineComment(line: string): string {
  // Same heuristic as Phase 57 — strip `// …` tail but preserve strings.
  // Simple: only strip when `//` occurs outside a string quote count.
  const idx = line.indexOf("//");
  if (idx === -1) return line;
  const before = line.slice(0, idx);
  const dq = (before.match(/"/g) || []).length;
  const sq = (before.match(/'/g) || []).length;
  const bt = (before.match(/`/g) || []).length;
  if (dq % 2 === 0 && sq % 2 === 0 && bt % 2 === 0) return before;
  return line;
}

for (const file of walk(SRC_ROOT)) {
  if (file === SELF_PATH) continue;
  const src = readFileSync(file, "utf8");

  // Guard 1: color literals
  if (!COLOR_LITERAL_ALLOWLIST.has(file)) {
    const lines = src.split("\n");
    lines.forEach((raw, i) => {
      const line = stripLineComment(raw);
      if ((HEX.test(line) || COLOR_FN.test(line)) && CONTEXT_HINT.test(line)) {
        violations.push({
          guard: "color-literal",
          file, line: i + 1, text: raw.trim(),
        });
      }
    });
  }

  // Guard 2: icon-size Button missing aria-label on the same element.
  // Walk each `<Button` opening, extract the full JSX opening tag respecting
  // brace/quote nesting, and flag if size is icon* and aria-label is absent.
  let m: RegExpExecArray | null;
  BUTTON_OPEN.lastIndex = 0;
  while ((m = BUTTON_OPEN.exec(src)) !== null) {
    const extracted = extractOpeningTag(src, m.index);
    if (!extracted) continue;
    const tag = extracted.tag;
    if (!ICON_SIZE.test(tag)) continue;
    if (/\baria-label\s*=/.test(tag)) continue;
    const pre = src.slice(0, m.index);
    const line = pre.split("\n").length;
    violations.push({
      guard: "icon-button-aria-label",
      file, line, text: tag.slice(0, 120).replace(/\s+/g, " "),
    });
  }
}

if (violations.length === 0) {
  console.log("PHASE-59 GUARDS OK");
  process.exit(0);
}
for (const v of violations) {
  console.log(`[${v.guard}] ${v.file}:${v.line}  ${v.text}`);
}
console.log(`PHASE-59 GUARDS FAIL: ${violations.length} violation(s)`);
process.exit(1);
