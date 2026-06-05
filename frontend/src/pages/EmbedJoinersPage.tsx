/**
 * EmbedJoinersPage — kiosk-friendly /embed/joiners. Sibling of
 * EmbedBirthdaysPage; renders just JoinersCard with no admin shell.
 * Defaults the UI language to German; ?lang=en to override.
 */
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { JoinersCard } from "@/components/dashboard/JoinersCard";

export function EmbedJoinersPage() {
  const { i18n } = useTranslation();
  useEffect(() => {
    const lang = new URLSearchParams(window.location.search).get("lang") ?? "de";
    if (i18n.language !== lang) {
      void i18n.changeLanguage(lang);
    }
  }, [i18n]);
  return (
    <div className="min-h-screen w-screen bg-background p-6">
      <JoinersCard embed />
    </div>
  );
}
