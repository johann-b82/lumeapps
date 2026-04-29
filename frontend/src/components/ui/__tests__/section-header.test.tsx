// Phase 57 Plan 01 — failing tests for SectionHeader primitive (TDD RED).
// Asserts h2/p shape, font-medium harmonization, lang attribute, null-safety,
// className pass-through, and zero `dark:` variants.
import { describe, it, expect, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { SectionHeader } from "@/components/ui/section-header";

beforeAll(async () => {
  if (!i18n.isInitialized) {
    await i18n.use(initReactI18next).init({
      resources: { en: { translation: {} } },
      lng: "en",
      fallbackLng: "en",
      keySeparator: false,
      interpolation: { escapeValue: false },
    });
  } else {
    await i18n.changeLanguage("en");
  }
});

describe("SectionHeader", () => {
  it("renders an h2 with the title text and font-medium class", () => {
    render(<SectionHeader title="My Title" description="My description" />);
    const heading = screen.getByRole("heading", { level: 2, name: "My Title" });
    expect(heading).toBeInTheDocument();
    expect(heading.className).toMatch(/\bfont-medium\b/);
  });

  it("renders a p with the description text and muted-foreground/text-xs styling", () => {
    const { container } = render(
      <SectionHeader title="T" description="The description" />,
    );
    const p = container.querySelector("p");
    expect(p).not.toBeNull();
    expect(p!.textContent).toBe("The description");
    expect(p!.className).toMatch(/\btext-muted-foreground\b/);
    expect(p!.className).toMatch(/\btext-xs\b/);
  });

  it("p carries lang attribute matching i18n.language", () => {
    const { container } = render(<SectionHeader title="T" description="D" />);
    const p = container.querySelector("p");
    expect(p).not.toBeNull();
    expect(p!.getAttribute("lang")).toBe(i18n.language);
  });

  it("returns null when title is empty string", () => {
    const { container } = render(<SectionHeader title="" description="anything" />);
    expect(container.firstChild).toBeNull();
  });

  it("applies consumer className to wrapper section", () => {
    const { container } = render(
      <SectionHeader title="T" description="D" className="my-custom-class" />,
    );
    const section = container.querySelector("section");
    expect(section).not.toBeNull();
    expect(section!.className).toMatch(/\bmy-custom-class\b/);
  });

  it("does not render any dark: Tailwind variants on its DOM nodes", () => {
    const { container } = render(<SectionHeader title="T" description="D" />);
    const all = container.querySelectorAll("*");
    all.forEach((el) => {
      expect(el.className.toString()).not.toMatch(/\bdark:/);
    });
  });
});
