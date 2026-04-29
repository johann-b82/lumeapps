import { Link, useParams } from "wouter";
import { useTranslation } from "react-i18next";
import { AdminOnly } from "@/auth/AdminOnly";
import { sections, type SectionId } from "@/lib/docs/registry";

function SectionGroup({
  titleKey,
  section,
  activeSection,
  activeSlug,
}: {
  titleKey: string;
  section: SectionId;
  activeSection: string | undefined;
  activeSlug: string | undefined;
}) {
  const { t } = useTranslation();
  const articles = sections[section];
  return (
    <div>
      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide px-2 mb-1">
        {t(titleKey)}
      </h3>
      <ul className="flex flex-col gap-0.5">
        {articles.map((a) => {
          const isActive = section === activeSection && a.slug === activeSlug;
          return (
            <li key={a.slug}>
              <Link
                href={`/docs/${section}/${a.slug}`}
                className={
                  isActive
                    ? "block px-2 py-1.5 rounded-md text-sm text-primary bg-accent font-medium"
                    : "block px-2 py-1.5 rounded-md text-sm text-foreground hover:bg-accent/10 transition-colors"
                }
              >
                {t(a.titleKey)}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function DocsSidebar() {
  const { section, slug } = useParams<{ section: string; slug: string }>();
  return (
    <nav className="w-56 shrink-0 hidden md:flex flex-col gap-6">
      <SectionGroup
        titleKey="docs.nav.userGuide"
        section="user-guide"
        activeSection={section}
        activeSlug={slug}
      />
      <AdminOnly>
        <SectionGroup
          titleKey="docs.nav.adminGuide"
          section="admin-guide"
          activeSection={section}
          activeSlug={slug}
        />
      </AdminOnly>
    </nav>
  );
}
