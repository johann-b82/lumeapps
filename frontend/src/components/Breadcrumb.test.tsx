import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n";
import { Breadcrumb } from "./Breadcrumb";

function renderAt(path: string) {
  const { hook } = memoryLocation({ path });
  return render(
    <I18nextProvider i18n={i18n}>
      <Router hook={hook}>
        <Breadcrumb />
      </Router>
    </I18nextProvider>,
  );
}

describe("Breadcrumb", () => {
  it("renders nothing on / (launcher)", () => {
    const { container } = renderAt("/");
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing on /login", () => {
    const { container } = renderAt("/login");
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing on unmapped route", () => {
    const { container } = renderAt("/foo");
    expect(container.firstChild).toBeNull();
  });

  it("renders one <nav> with one <ol> on /sales", () => {
    const { container } = renderAt("/sales");
    const navs = container.querySelectorAll("nav");
    expect(navs).toHaveLength(1);
    const ols = container.querySelectorAll("ol");
    expect(ols).toHaveLength(1);
  });

  it("renders Home + Sales = 2 <li> on /sales", () => {
    const { container } = renderAt("/sales");
    const items = container.querySelectorAll("li");
    expect(items).toHaveLength(2);
  });

  it("last crumb on /sales is <span aria-current='page'> (D-06)", () => {
    const { container } = renderAt("/sales");
    const items = container.querySelectorAll("li");
    const last = items[items.length - 1];
    const span = last.querySelector("[aria-current='page']");
    expect(span).not.toBeNull();
    expect(span?.tagName).toBe("SPAN");
  });

  it("first crumb on /sales is <a href='/'> (Home link, D-04)", () => {
    const { container } = renderAt("/sales");
    const firstLi = container.querySelectorAll("li")[0];
    const a = firstLi.querySelector("a");
    expect(a).not.toBeNull();
    expect(a?.getAttribute("href")).toBe("/");
  });

  it("renders exactly 3 <li> on /settings/sensors", () => {
    const { container } = renderAt("/settings/sensors");
    const items = container.querySelectorAll("li");
    expect(items).toHaveLength(3);
  });

  it("renders (crumbs.length - 1) ChevronRight separators with aria-hidden", () => {
    const { container } = renderAt("/settings/sensors"); // 3 crumbs
    // aria-hidden chevrons
    const hidden = container.querySelectorAll("[aria-hidden='true']");
    expect(hidden.length).toBe(2);
  });

  it("first <li> has no separator before it", () => {
    const { container } = renderAt("/sales");
    const firstLi = container.querySelectorAll("li")[0];
    // No aria-hidden svg inside first li
    const hiddenInFirst = firstLi.querySelector("[aria-hidden='true']");
    expect(hiddenInFirst).toBeNull();
  });

  it("last <li> has no separator after it (separator is before subsequent li, not after last)", () => {
    const { container } = renderAt("/sales");
    const items = container.querySelectorAll("li");
    const last = items[items.length - 1];
    // last li should not contain an aria-current span AND a trailing chevron — just the span
    const trailingChevron = last.querySelector("span[aria-current='page'] ~ [aria-hidden='true']");
    expect(trailingChevron).toBeNull();
  });

  it("non-leaf <a> elements carry focus-visible ring classes", () => {
    const { container } = renderAt("/settings/sensors");
    const anchors = container.querySelectorAll("a");
    expect(anchors.length).toBeGreaterThan(0);
    anchors.forEach((a) => {
      const cls = a.className;
      expect(cls).toMatch(/focus-visible:ring-2/);
      expect(cls).toMatch(/focus-visible:ring-ring/);
    });
  });

  it("non-leaf crumbs render as wouter <Link> (native <a> with href)", () => {
    const { container } = renderAt("/settings/sensors");
    // 3 crumbs → 2 anchors (Home + Settings); last is span
    const anchors = container.querySelectorAll("a");
    expect(anchors).toHaveLength(2);
    expect(anchors[0].getAttribute("href")).toBe("/");
    expect(anchors[1].getAttribute("href")).toBe("/settings");
  });

  it("renders 2 <li> on /signage/playlists/abc-123 + Home = 3 li (D-02 dynamic collapse)", () => {
    const { container } = renderAt("/signage/playlists/abc-123");
    const items = container.querySelectorAll("li");
    expect(items).toHaveLength(3);
  });
});
