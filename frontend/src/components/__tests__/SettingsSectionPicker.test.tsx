import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n";
import { SettingsDraftProvider } from "@/contexts/SettingsDraftContext";
import { SettingsSectionPicker } from "@/components/SettingsSectionPicker";

function renderAt(path: string) {
  const memory = memoryLocation({ path, record: true });
  return {
    memory,
    ...render(
      <I18nextProvider i18n={i18n}>
        <SettingsDraftProvider>
          <Router hook={memory.hook}>
            <SettingsSectionPicker />
          </Router>
        </SettingsDraftProvider>
      </I18nextProvider>,
    ),
  };
}

describe("SettingsSectionPicker", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("{}", { status: 200 }),
    );
  });

  it("renders the trigger with data-testid='settings-section-picker-trigger'", () => {
    renderAt("/settings/general");
    expect(
      screen.getByTestId("settings-section-picker-trigger"),
    ).toBeInTheDocument();
  });

  it("trigger shows the translated label for the active section (not the raw id)", () => {
    renderAt("/settings/hr");
    const trigger = screen.getByTestId("settings-section-picker-trigger");
    expect(trigger.textContent ?? "").not.toContain("hr");
    expect(trigger.textContent ?? "").toContain(i18n.t("settings.section.hr"));
  });

  it("selecting an option (clean state) navigates to the matching path", async () => {
    const { memory } = renderAt("/settings/general");
    const trigger = screen.getByTestId("settings-section-picker-trigger");
    await userEvent.click(trigger);
    // base-ui Select renders options in a portal that flips from `hidden`
    // to visible on open — race-prone with sync getByRole in the full
    // suite. findByRole waits for the popup to mount.
    const hrOption = await screen.findByRole("option", { name: /HR/i });
    await userEvent.click(hrOption);
    expect(memory.history).toContain("/settings/hr");
  });
});
