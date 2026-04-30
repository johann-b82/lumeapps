import { Link, useLocation } from "wouter";
import { useTranslation } from "react-i18next";
import { BookOpenText } from "lucide-react";
import { Breadcrumb } from "@/components/Breadcrumb";
import { UserMenu } from "@/components/UserMenu";
import { LanguageToggle } from "@/components/LanguageToggle";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useSettings } from "@/hooks/useSettings";
import { DEFAULT_SETTINGS } from "@/lib/defaults";
import { cn } from "@/lib/utils";

export function NavBar() {
  const [location] = useLocation();
  const { t } = useTranslation();
  const isLauncher = location === "/";
  const { data } = useSettings();
  const settings = data ?? DEFAULT_SETTINGS;

  return (
    <nav className="fixed top-0 inset-x-0 h-16 bg-card border-b border-border z-50">
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2 cursor-pointer">
          {settings.logo_url != null && (
            <img
              src={settings.logo_url}
              alt={settings.app_name}
              className="max-h-8 max-w-8 object-contain"
            />
          )}
          <span className="text-sm font-medium">{settings.app_name}</span>
        </Link>
        {!isLauncher && (
          <div data-testid="navbar-breadcrumb-wrapper" className="hidden md:block">
            <Breadcrumb />
          </div>
        )}
        <div className="ml-auto flex items-center gap-4">
          <ThemeToggle />
          <LanguageToggle />
          <Link
            href="/docs"
            aria-label={t("docs.nav.docsLabel")}
            className={cn(
              "inline-flex items-center justify-center rounded-full size-8 bg-muted text-foreground",
              "hover:bg-accent/20 transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
          >
            <BookOpenText className="h-5 w-5" aria-hidden="true" />
          </Link>
          <UserMenu />
        </div>
      </div>
    </nav>
  );
}
