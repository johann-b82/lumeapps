import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { TocEntry } from "../../lib/docs/toc";

interface Props {
  entries: TocEntry[];
}

export function TableOfContents({ entries }: Props) {
  const { t } = useTranslation();
  const [activeId, setActiveId] = useState<string>("");

  useEffect(() => {
    const headings = entries
      .map((e) => document.getElementById(e.id))
      .filter(Boolean) as HTMLElement[];
    if (headings.length === 0) return;

    const observer = new IntersectionObserver(
      (observerEntries) => {
        const visible = observerEntries.find((e) => e.isIntersecting);
        if (visible) setActiveId(visible.target.id);
      },
      { rootMargin: "0px 0px -60% 0px", threshold: 0.1 }
    );
    headings.forEach((h) => observer.observe(h));
    return () => observer.disconnect();
  }, [entries]);

  if (entries.length === 0) return null;

  return (
    <nav aria-label="Table of contents">
      <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
        {t("docs.toc.title")}
      </p>
      <ol className="space-y-1 text-sm border-l border-border">
        {entries.map((entry) => (
          <li key={entry.id}>
            <a
              href={`#${entry.id}`}
              className={[
                "block py-1 transition-colors",
                entry.level === 3 ? "pl-6" : "pl-3",
                activeId === entry.id
                  ? "border-l-2 border-primary text-primary -ml-px"
                  : "text-muted-foreground hover:text-foreground",
              ].join(" ")}
            >
              {entry.text}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
