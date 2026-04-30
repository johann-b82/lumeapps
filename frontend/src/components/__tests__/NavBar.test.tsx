import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { I18nextProvider } from "react-i18next";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18n from "@/i18n";
import { NavBar } from "@/components/NavBar";

// Stub browser APIs not available in jsdom
beforeAll(() => {
  if (!("ResizeObserver" in globalThis)) {
    globalThis.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }
  if (!window.matchMedia) {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
    });
  }
});

vi.mock("@/auth/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "tester@example.com", role: "admin" },
    signOut: vi.fn(),
  }),
}));

function renderAt(path: string) {
  const { hook } = memoryLocation({ path });
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>
        <Router hook={hook}>
          <NavBar />
        </Router>
      </I18nextProvider>
    </QueryClientProvider>,
  );
}

describe("NavBar", () => {
  it("breadcrumb wrapper has hidden md:block (mobile-hide contract)", () => {
    renderAt("/sales");
    const wrapper = screen.getByTestId("navbar-breadcrumb-wrapper");
    expect(wrapper).toHaveClass("hidden", "md:block");
  });

  it("ThemeToggle wrapper has hidden md:flex", () => {
    renderAt("/sales");
    const themeRadiogroup = screen.getByLabelText(i18n.t("theme.toggle.aria_label"));
    const wrapper = themeRadiogroup.closest("div.hidden.md\\:flex");
    expect(wrapper).not.toBeNull();
  });

  it("LanguageToggle wrapper has hidden md:flex", () => {
    renderAt("/sales");
    const langRadiogroup = screen.getByLabelText(/language/i);
    const wrapper = langRadiogroup.closest("div.hidden.md\\:flex");
    expect(wrapper).not.toBeNull();
  });
});
