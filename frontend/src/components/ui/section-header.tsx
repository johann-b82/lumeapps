// Phase 57 Plan 01 — SectionHeader primitive.
// Reusable heading + description block consumed by every admin section
// (SECTION-01). Pure, non-interactive, null-safe. Harmonizes typography
// to font-medium per UI-SPEC §Typography (replaces ad-hoc font-semibold
// in PlaylistEditorPage SOTT). Token-driven colors only — zero `dark:`
// variants. The <p> carries lang={i18n.language} so the browser can
// hyphenate descriptions correctly across DE/EN switches.
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

interface SectionHeaderProps {
  title: string;
  description: string;
  className?: string;
  children?: never;
}

export function SectionHeader({ title, description, className }: SectionHeaderProps) {
  const { i18n } = useTranslation();
  if (!title) return null;
  return (
    <section className={cn("mb-6", className)}>
      <h2 className="text-base font-medium text-foreground">{title}</h2>
      <p className="mt-1 text-xs text-muted-foreground" lang={i18n.language}>
        {description}
      </p>
    </section>
  );
}
