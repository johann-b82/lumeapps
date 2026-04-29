import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import { Trash2 } from "lucide-react";
import i18n from "@/i18n";
import { DeleteButton, TrashIcon } from "../delete-button";

beforeAll(() => {
  // Preload i18n keys that Plan 57-04 will add.
  i18n.addResource("en", "translation", "ui.delete.title", "Delete");
  i18n.addResource("en", "translation", "ui.delete.cancel", "Cancel");
  i18n.addResource("en", "translation", "ui.delete.confirm", "Delete");
  i18n.addResource(
    "en",
    "translation",
    "ui.delete.bodyFallback",
    "Are you sure you want to delete <1>{{itemLabel}}</1>?",
  );
  i18n.addResource("de", "translation", "ui.delete.title", "Löschen");
  i18n.addResource("de", "translation", "ui.delete.cancel", "Abbrechen");
  i18n.addResource("de", "translation", "ui.delete.confirm", "Löschen");
  i18n.addResource(
    "de",
    "translation",
    "ui.delete.bodyFallback",
    "Bist du sicher, dass du <1>{{itemLabel}}</1> löschen möchtest?",
  );
});

function renderButton(
  props: Partial<React.ComponentProps<typeof DeleteButton>> = {},
) {
  const defaults: React.ComponentProps<typeof DeleteButton> = {
    itemLabel: "playlist-A",
    onConfirm: vi.fn(),
    "aria-label": "Delete playlist-A",
  };
  const merged = { ...defaults, ...props };
  const utils = render(
    <I18nextProvider i18n={i18n}>
      <DeleteButton {...merged} />
    </I18nextProvider>,
  );
  return { ...utils, props: merged };
}

describe("DeleteButton", () => {
  it("renders a trigger button with the consumer-provided aria-label", () => {
    renderButton({ "aria-label": "Delete media-Foo" });
    expect(
      screen.getByRole("button", { name: "Delete media-Foo" }),
    ).toBeInTheDocument();
  });

  it("renders a Trash2 icon (svg present, aria-hidden)", () => {
    renderButton();
    const trigger = screen.getByRole("button", { name: "Delete playlist-A" });
    const svg = trigger.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg).toHaveAttribute("aria-hidden", "true");
  });

  it("clicking the trigger opens the dialog", async () => {
    const user = userEvent.setup();
    renderButton();
    // Title not rendered before open
    expect(screen.queryByRole("heading", { name: "Delete" })).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "Delete playlist-A" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Delete" }),
    ).toBeInTheDocument();
  });

  it("itemLabel appears inside the dialog body in a strong element", async () => {
    const user = userEvent.setup();
    renderButton({ itemLabel: "summer-promo.mp4" });
    await user.click(screen.getByRole("button", { name: "Delete playlist-A" }));
    const strong = await screen.findByText("summer-promo.mp4");
    expect(strong.tagName).toBe("STRONG");
  });

  it("clicking Confirm calls onConfirm", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    renderButton({ onConfirm });
    await user.click(screen.getByRole("button", { name: "Delete playlist-A" }));
    const confirm = await screen.findByRole("button", { name: "Delete" });
    await user.click(confirm);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("closes the dialog after onConfirm resolves", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn(() => Promise.resolve());
    renderButton({ onConfirm });
    await user.click(screen.getByRole("button", { name: "Delete playlist-A" }));
    const confirm = await screen.findByRole("button", { name: "Delete" });
    await user.click(confirm);
    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: "Cancel" }),
      ).not.toBeInTheDocument();
    });
  });

  it("closes the dialog after onConfirm rejects (caller handles error)", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn(() => Promise.reject(new Error("boom")));
    renderButton({ onConfirm });
    await user.click(screen.getByRole("button", { name: "Delete playlist-A" }));
    const confirm = await screen.findByRole("button", { name: "Delete" });
    // userEvent surfaces the rejection — swallow at the test boundary.
    await user.click(confirm).catch(() => {});
    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: "Cancel" }),
      ).not.toBeInTheDocument();
    });
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("disables the trigger when disabled prop is true", () => {
    renderButton({ disabled: true });
    expect(
      screen.getByRole("button", { name: "Delete playlist-A" }),
    ).toBeDisabled();
  });

  it("TrashIcon is the lucide Trash2 component (re-export)", () => {
    expect(TrashIcon).toBe(Trash2);
  });
});
