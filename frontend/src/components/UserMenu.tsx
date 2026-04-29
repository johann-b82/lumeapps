import { useTranslation } from "react-i18next";
import { LogOut, User as UserIcon } from "lucide-react";
import { Link as WouterLink } from "wouter";
import { Menu as MenuPrimitive } from "@base-ui/react/menu";

import {
  Dropdown,
  DropdownTrigger,
  DropdownContent,
  DropdownItem,
  DropdownSeparator,
} from "@/components/ui/dropdown";
import { useAuth } from "@/auth/useAuth";
import { cn } from "@/lib/utils";

/**
 * Derive avatar initials from an email local-part.
 *
 * - "johann.bechtold@x" -> "JB"
 * - "admin@x"           -> "AD"   (single part: first two chars uppercased)
 * - "a.b.c@x"           -> "AB"   (first two parts' first letters)
 * - "@empty.com"        -> null   (empty local-part -> caller falls back to icon)
 */
export function initialsFrom(email: string): string | null {
  const local = email.split("@")[0];
  if (!local) return null;
  const parts = local.split(/[.\-_]+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return local.slice(0, 2).toUpperCase();
}

/**
 * UserMenu — circular 36px avatar trigger backed by the Phase 55 Dropdown
 * primitive. Opens a right-aligned menu containing:
 *   1. Identity header (<div>, NOT a menuitem — D-12 #1)
 *   2. Separator
 *   3. Documentation row (client-side wouter nav via Menu.LinkItem render prop)
 *   4. Settings row (client-side wouter nav)
 *   5. Separator
 *   6. Sign out (calls useAuth().signOut)
 *
 * First real consumer of the Phase 55 Dropdown primitive (D-13).
 * No Tailwind dark-variants — tokens only.
 */
export function UserMenu() {
  const { t } = useTranslation();
  const { user, signOut } = useAuth();
  if (!user) return null;

  const initials = initialsFrom(user.email);
  const localPart = user.email.split("@")[0];

  return (
    <Dropdown>
      <DropdownTrigger
        aria-label={t("userMenu.triggerLabel")}
        className={cn(
          "inline-flex items-center justify-center rounded-full size-8 bg-muted text-sm font-normal",
          "hover:bg-accent/20 transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        {initials ?? <UserIcon className="h-5 w-5" aria-hidden />}
      </DropdownTrigger>
      <DropdownContent align="end" className="min-w-56">
        <div
          className="px-2 py-1.5 text-xs text-muted-foreground"
          data-testid="usermenu-identity"
        >
          <div className="font-medium text-foreground truncate">{localPart}</div>
          <div className="truncate">{user.email}</div>
        </div>
        <DropdownSeparator />
        <MenuPrimitive.LinkItem
          href="/docs"
          render={<WouterLink href="/docs" />}
          className={cn(
            "relative flex cursor-default select-none items-center gap-2 rounded-md px-2 py-1 text-sm outline-none",
            "data-[highlighted]:bg-muted data-[highlighted]:text-foreground",
          )}
        >
          {t("userMenu.docs")}
        </MenuPrimitive.LinkItem>
        <MenuPrimitive.LinkItem
          href="/settings"
          render={<WouterLink href="/settings" />}
          className={cn(
            "relative flex cursor-default select-none items-center gap-2 rounded-md px-2 py-1 text-sm outline-none",
            "data-[highlighted]:bg-muted data-[highlighted]:text-foreground",
          )}
        >
          {t("userMenu.settings")}
        </MenuPrimitive.LinkItem>
        <DropdownSeparator />
        <DropdownItem
          onClick={() => void signOut()}
          className="text-destructive data-[highlighted]:text-destructive"
        >
          <LogOut className="h-4 w-4" aria-hidden />
          {t("userMenu.signOut")}
        </DropdownItem>
      </DropdownContent>
    </Dropdown>
  );
}
