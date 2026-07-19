import { useTranslation } from "react-i18next";

/**
 * Minimal manual pager for client-side paginated tables (prev/next + summary).
 * Renders nothing when there is at most one page. `page` is 0-based.
 */
export function Pager({ page, pageCount, total, onPage }: {
  page: number;
  pageCount: number;
  total: number;
  onPage: (p: number) => void;
}) {
  const { t } = useTranslation();
  if (pageCount <= 1) return null;
  return (
    <div className="flex items-center justify-between mt-3 text-sm">
      <span className="text-muted-foreground">
        {t("pagination.summary", { page: page + 1, pages: pageCount, total })}
      </span>
      <div className="flex gap-2">
        <button className="px-3 py-1 border rounded disabled:opacity-40"
          disabled={page <= 0} onClick={() => onPage(page - 1)}>
          {t("pagination.prev")}
        </button>
        <button className="px-3 py-1 border rounded disabled:opacity-40"
          disabled={page >= pageCount - 1} onClick={() => onPage(page + 1)}>
          {t("pagination.next")}
        </button>
      </div>
    </div>
  );
}
