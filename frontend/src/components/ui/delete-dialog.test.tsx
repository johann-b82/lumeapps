import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n";
import { DeleteDialog } from "./delete-dialog";

beforeAll(() => {
  // Preload i18n keys that Plan 57-04 will add.
  i18n.addResource("en", "translation", "ui.delete.title", "Delete");
  i18n.addResource("en", "translation", "ui.delete.cancel", "Cancel");
  i18n.addResource("en", "translation", "ui.delete.confirm", "Delete");
  i18n.addResource("de", "translation", "ui.delete.title", "Löschen");
  i18n.addResource("de", "translation", "ui.delete.cancel", "Abbrechen");
  i18n.addResource("de", "translation", "ui.delete.confirm", "Löschen");
});

function renderDialog(props: Partial<React.ComponentProps<typeof DeleteDialog>> = {}) {
  const defaults = {
    open: true,
    onOpenChange: vi.fn(),
    body: <span>Are you sure?</span>,
    onConfirm: vi.fn(),
  };
  const merged = { ...defaults, ...props };
  const utils = render(
    <I18nextProvider i18n={i18n}>
      <DeleteDialog {...merged} />
    </I18nextProvider>,
  );
  return { ...utils, props: merged };
}

describe("DeleteDialog", () => {
  it("renders default DialogTitle from t('ui.delete.title') when no title prop", async () => {
    renderDialog();
    const title = await screen.findByRole("heading");
    expect(title).toHaveTextContent("Delete");
  });

  it("renders provided body ReactNode", async () => {
    renderDialog({ body: <span>Custom body content</span> });
    expect(await screen.findByText("Custom body content")).toBeInTheDocument();
  });

  it("autoFocuses the Cancel button on open (D-05)", async () => {
    renderDialog();
    const cancel = await screen.findByRole("button", { name: "Cancel" });
    // React strips the `autofocus` HTML attribute and instead calls .focus()
    // on mount. base-ui Dialog manages focus, but Cancel having autoFocus
    // ensures it claims the initial focus over Confirm.
    await new Promise((r) => setTimeout(r, 50));
    expect(document.activeElement).toBe(cancel);
  });

  it("Cancel button uses outline variant", async () => {
    renderDialog();
    const cancel = await screen.findByRole("button", { name: "Cancel" });
    // shadcn Button outline variant: includes 'border' class fragment
    expect(cancel.className).toMatch(/border/);
  });

  it("Confirm button uses destructive variant (D-06)", async () => {
    renderDialog();
    const confirm = await screen.findByRole("button", { name: "Delete" });
    // destructive variant adds 'bg-destructive' class fragment
    expect(confirm.className).toMatch(/bg-destructive/);
  });

  it("calls onConfirm when Confirm clicked", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    renderDialog({ onConfirm });
    const confirm = await screen.findByRole("button", { name: "Delete" });
    await user.click(confirm);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("calls onOpenChange(false) and NOT onConfirm when Cancel clicked", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onConfirm = vi.fn();
    renderDialog({ onOpenChange, onConfirm });
    const cancel = await screen.findByRole("button", { name: "Cancel" });
    await user.click(cancel);
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("disables the Confirm button when confirmDisabled=true", async () => {
    renderDialog({ confirmDisabled: true });
    const confirm = await screen.findByRole("button", { name: "Delete" });
    expect(confirm).toBeDisabled();
  });

  it("uses provided title/cancelLabel/confirmLabel overrides", async () => {
    renderDialog({
      title: "Remove item",
      cancelLabel: "Keep",
      confirmLabel: "Remove",
    });
    expect(await screen.findByText("Remove item")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Keep" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
  });
});
