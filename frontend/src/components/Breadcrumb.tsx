import { Link, useLocation } from "wouter";
import { useTranslation } from "react-i18next";
import { ChevronRight } from "lucide-react";
import { matchBreadcrumb } from "@/lib/breadcrumbs";
import { cn } from "@/lib/utils";

/**
 * Breadcrumb trail for the current route. Renders nothing on the launcher
 * (`/`), login, or unmapped routes (D-03).
 *
 * Home crumb is always prepended (D-04). Non-leaf crumbs render as wouter
 * <Link> (real <a>, Tab/Enter navigable, HDR-03). Leaf crumb renders as
 * <span aria-current="page"> (D-06). Separator is a lucide ChevronRight
 * marked aria-hidden (D-05).
 *
 * Phase 56 Plan 01 — HDR-02, HDR-03.
 */
export function Breadcrumb() {
  const { t } = useTranslation();
  const [location] = useLocation();
  const trail = matchBreadcrumb(location);
  if (!trail) return null;

  // Prepend implicit Home crumb (D-04). Home is always a link — never the leaf.
  const crumbs = [{ labelKey: "nav.home", href: "/" }, ...trail];

  return (
    <nav
      aria-label={t("breadcrumb.aria_label")}
      className="flex items-center gap-1.5 text-sm"
    >
      <ol className="flex items-center gap-1.5">
        {crumbs.map((c, idx) => {
          const isLast = idx === crumbs.length - 1;
          return (
            <li key={idx} className="flex items-center gap-1.5">
              {idx > 0 && (
                <ChevronRight
                  aria-hidden
                  className="h-4 w-4 text-muted-foreground"
                />
              )}
              {isLast ? (
                <span
                  aria-current="page"
                  className="text-primary font-medium"
                >
                  {t(c.labelKey)}
                </span>
              ) : (
                <Link
                  href={c.href ?? "/"}
                  className={cn(
                    "text-foreground hover:text-primary transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded",
                  )}
                >
                  {t(c.labelKey)}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
