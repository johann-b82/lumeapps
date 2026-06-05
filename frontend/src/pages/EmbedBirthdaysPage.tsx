/**
 * EmbedBirthdaysPage — kiosk-friendly /embed/birthdays.
 *
 * Strips the full admin shell (no NavBar, no SubHeader, no AuthGate) and
 * just renders BirthdaysCard against the unauthenticated /api/hr/embed
 * endpoints. Designed to be iframed from a signage URL playlist item.
 *
 * Defaults the UI language to German (corporate display); honour ?lang=en
 * if the operator pastes a different locale.
 */
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { BirthdaysCard } from "@/components/dashboard/BirthdaysCard";

export function EmbedBirthdaysPage() {
  const { i18n } = useTranslation();
  useEffect(() => {
    const lang = new URLSearchParams(window.location.search).get("lang") ?? "de";
    if (i18n.language !== lang) {
      void i18n.changeLanguage(lang);
    }
  }, [i18n]);
  return (
    <div className="min-h-screen w-screen bg-background p-6">
      <BirthdaysCard embed />
    </div>
  );
}
