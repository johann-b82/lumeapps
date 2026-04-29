import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { fetchLatestUpload } from "@/lib/api";
import { kpiKeys } from "@/lib/queryKeys";

export function FreshnessIndicator() {
  const { t, i18n } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: kpiKeys.latestUpload(),
    queryFn: fetchLatestUpload,
  });

  if (isLoading) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  if (!data?.uploaded_at) {
    return (
      <span className="text-xs text-muted-foreground">
        {t("nav.lastUpdated.never")}
      </span>
    );
  }
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const formatted = new Intl.DateTimeFormat(locale, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(data.uploaded_at));
  return (
    <span className="text-xs text-muted-foreground">
      {t("nav.lastUpdated")} {formatted}
    </span>
  );
}
