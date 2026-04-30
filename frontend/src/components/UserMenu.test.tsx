import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n";
import { AuthContext, type AuthState } from "@/auth/AuthContext";
import { UserMenu, initialsFrom } from "./UserMenu";

function withAuth(user: { email: string } | null, signOut = vi.fn()) {
  const value: AuthState = {
    user: user ? { id: "u1", email: user.email, role: "admin" } : null,
    role: user ? "admin" : null,
    isLoading: false,
    signIn: vi.fn(),
    signOut,
  };
  return render(
    <I18nextProvider i18n={i18n}>
      <AuthContext.Provider value={value}>
        <UserMenu />
      </AuthContext.Provider>
    </I18nextProvider>,
  );
}

describe("initialsFrom", () => {
  it("two parts -> two initials", () => {
    expect(initialsFrom("johann.bechtold@x")).toBe("JB");
  });
  it("single part -> first two chars", () => {
    expect(initialsFrom("admin@x")).toBe("AD");
  });
  it("three parts -> first two parts' initials", () => {
    expect(initialsFrom("a.b.c@d.e")).toBe("AB");
  });
  it("empty local-part -> null", () => {
    expect(initialsFrom("@empty.com")).toBeNull();
  });
});

describe("UserMenu", () => {
  it("returns null when user is null", () => {
    const { container } = withAuth(null);
    expect(container.firstChild).toBeNull();
  });

  it("renders JB initials for johann.bechtold@...", () => {
    withAuth({ email: "johann.bechtold@example.com" });
    const trigger = document.querySelector("[aria-label]");
    expect(trigger?.textContent).toBe("JB");
  });

  it("renders AD initials for admin@...", () => {
    withAuth({ email: "admin@example.com" });
    const trigger = document.querySelector("[aria-label]");
    expect(trigger?.textContent).toBe("AD");
  });

  it("opens menu on trigger click and shows identity header", async () => {
    withAuth({ email: "a.b@c.d" });
    const trigger = document.querySelector("[aria-label]") as HTMLElement;
    await userEvent.click(trigger);
    expect(await screen.findByTestId("usermenu-identity")).toBeInTheDocument();
  });

  it("calls signOut on Sign out click", async () => {
    const signOut = vi.fn().mockResolvedValue(undefined);
    withAuth({ email: "a.b@c.d" }, signOut);
    const trigger = document.querySelector("[aria-label]") as HTMLElement;
    await userEvent.click(trigger);
    const items = await screen.findAllByRole("menuitem");
    // Sign out is the LAST menuitem (identity header is NOT a menuitem per D-12)
    await userEvent.click(items[items.length - 1]);
    expect(signOut).toHaveBeenCalledTimes(1);
  });
});

describe("UserMenu mobile-only theme + language items", () => {
  it("renders theme + language menu items wrapped with md:hidden", async () => {
    withAuth({ email: "a.b@c.d" });
    const trigger = document.querySelector("[aria-label]") as HTMLElement;
    fireEvent.click(trigger);
    const theme = await screen.findByTestId("usermenu-theme-item");
    const lang = await screen.findByTestId("usermenu-language-item");
    expect(theme).toHaveClass("md:hidden");
    expect(lang).toHaveClass("md:hidden");
  });
});
