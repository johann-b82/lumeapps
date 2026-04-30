import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { I18nextProvider } from "react-i18next";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18n from "@/i18n";
import { SubHeader } from "@/components/SubHeader";
import { DateRangeProvider } from "@/contexts/DateRangeContext";

function renderAt(path: string) {
  const memory = memoryLocation({ path, record: true });
  const qc = new QueryClient();
  return {
    memory,
    ...render(
      <QueryClientProvider client={qc}>
        <I18nextProvider i18n={i18n}>
          <DateRangeProvider>
            <Router hook={memory.hook}>
              <SubHeader />
            </Router>
          </DateRangeProvider>
        </I18nextProvider>
      </QueryClientProvider>,
    ),
  };
}

describe("SubHeader signage tabs", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    );
  });

  it("renders a Select trigger on a signage admin tab route", () => {
    renderAt("/signage/playlists");
    expect(screen.getByTestId("signage-tabs-trigger")).toBeInTheDocument();
  });

  it("does not render signage tabs on /signage/pair", () => {
    renderAt("/signage/pair");
    expect(screen.queryByTestId("signage-tabs-trigger")).toBeNull();
  });

  it("trigger shows the translated label for the active tab (not the raw id)", () => {
    renderAt("/signage/playlists");
    const trigger = screen.getByTestId("signage-tabs-trigger");
    expect(trigger.textContent ?? "").not.toContain("playlists");
    expect(trigger.textContent ?? "").toContain(
      i18n.t("signage.admin.nav.playlists"),
    );
  });

  it("Select navigates via wouter on change", async () => {
    const { memory } = renderAt("/signage/playlists");
    const trigger = screen.getByTestId("signage-tabs-trigger");
    await userEvent.click(trigger);
    await userEvent.click(screen.getByRole("option", { name: /devices/i }));
    expect(memory.history).toContain("/signage/devices");
  });
});
