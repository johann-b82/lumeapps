import { useEffect, useMemo } from "react";
import { useParams, useLocation } from "wouter";
import { useTranslation } from "react-i18next";
import { useRole } from "@/auth/useAuth";
import { MarkdownRenderer } from "../components/docs/MarkdownRenderer";
import { TableOfContents } from "../components/docs/TableOfContents";
import { DocsSidebar } from "../components/docs/DocsSidebar";
import { extractToc } from "../lib/docs/toc";
import { registry } from "../lib/docs/registry";

export default function DocsPage() {
  const { section, slug } = useParams<{ section: string; slug: string }>();
  const role = useRole();
  const [, navigate] = useLocation();
  const { i18n } = useTranslation();
  const lang = i18n.language.startsWith("de") ? "de" : "en";

  // D-07: Bare /docs → role-aware redirect
  useEffect(() => {
    if (!section || !slug) {
      navigate(
        role === "admin"
          ? "/docs/admin-guide/intro"
          : "/docs/user-guide/intro",
        { replace: true }
      );
    }
  }, [section, slug, role, navigate]);

  // D-03: Viewer on admin-guide → silent redirect to user guide intro.
  // role === null means auth hasn't hydrated yet (or just cleared); don't
  // treat that as "not admin" or we'd bounce /docs/admin-guide/* away while
  // AuthGate is still about to take over and redirect to /login.
  useEffect(() => {
    if (role === null) return;
    if (section === "admin-guide" && role !== "admin") {
      navigate("/docs/user-guide/intro", { replace: true });
    }
  }, [section, role, navigate]);

  // Guard render while redirecting (prevent flash per Pitfall 4)
  if (!section || !slug) return null;
  if (role === null) return null;
  if (section === "admin-guide" && role !== "admin") return null;

  const content = registry[lang]?.[section]?.[slug]
    ?? registry["en"]?.[section]?.[slug]
    ?? "";

  const tocEntries = useMemo(() => extractToc(content), [content]);

  return (
    <div className="flex gap-8 px-6 py-8 max-w-7xl mx-auto">
      <DocsSidebar />
      <article className="flex-1 min-w-0">
        <MarkdownRenderer content={content} />
      </article>
      <aside className="sticky top-24 hidden lg:block w-60 shrink-0">
        <TableOfContents entries={tocEntries} />
      </aside>
    </div>
  );
}
