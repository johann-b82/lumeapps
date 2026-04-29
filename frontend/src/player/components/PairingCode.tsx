// Phase 47 UI-SPEC §Typography: pairing code at 256px (16rem) monospace, semibold, tracking 0.05em.
// Distance-readability target: >= 5m on a 1080p panel (CONTEXT D-3 + UI-SPEC §Typography rationale).
// Pure presentational — props in, JSX out. No effects, no state.

import { t } from "@/player/lib/strings";

export interface PairingCodeProps {
  /** "XXX-XXX" formatted code, or null while the request is in flight. */
  code: string | null;
}

export function PairingCode({ code }: PairingCodeProps) {
  // ARIA per UI-SPEC §Accessibility: code is rendered inside <output aria-live="polite">.
  return (
    <output
      aria-live="polite"
      aria-label="Pairing code"
      className="text-[16rem] font-mono font-semibold tracking-[0.05em] leading-none text-neutral-50"
    >
      {code ?? t("pair.code_placeholder")}
    </output>
  );
}
