import { useTranslation } from "react-i18next";
import type { ValidationErrorDetail } from "@/lib/api";

interface ErrorListProps {
  errors: ValidationErrorDetail[];
}

export function ErrorList({ errors }: ErrorListProps) {
  const { t } = useTranslation();

  if (errors.length === 0) {
    return null;
  }

  return (
    <div className="border-l-4 border-destructive pl-4 py-2">
      <p className="text-sm font-semibold text-destructive mb-2">
        {t("error_heading", { count: errors.length })}
      </p>
      <ul
        className="max-h-[240px] overflow-y-auto space-y-1"
        aria-label={t("error_heading", { count: errors.length })}
      >
        {errors.map((e, idx) => (
          <li key={idx} className="text-sm text-foreground">
            {e.column
              ? t("error_row_format", { row: e.row, column: e.column, message: e.message })
              : t("error_row_no_col_format", { row: e.row, message: e.message })}
          </li>
        ))}
      </ul>
    </div>
  );
}
