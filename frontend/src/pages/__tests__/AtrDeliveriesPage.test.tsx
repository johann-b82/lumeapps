// frontend/src/pages/__tests__/AtrDeliveriesPage.test.tsx
import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { describe, it, expect, vi, beforeEach } from "vitest";
import i18n from "@/i18n";
import { AtrDeliveriesPage } from "../AtrDeliveriesPage";
import * as atrApi from "@/lib/atrApi";

vi.mock("@/lib/atrApi");

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const mem = memoryLocation({ path: "/atr/deliveries" });
  return (
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}><Router hook={mem.hook}>{ui}</Router></I18nextProvider>
    </QueryClientProvider>
  );
}

describe("AtrDeliveriesPage", () => {
  beforeEach(() => vi.resetAllMocks());
  it("lists deliveries", async () => {
    vi.mocked(atrApi.fetchInputFiles).mockResolvedValue({ configured: false, files: [] });
    vi.mocked(atrApi.fetchDeliveries).mockResolvedValue([{
      id: 7, source_filename: "LS.pdf", ba_auftrag: "1024738",
      compartment: "CCRC", atr_number: null, container_number: "AK111000", msn: null,
      status: "draft", created_at: "2026-06-25T10:00:00Z",
    }]);
    render(wrap(<AtrDeliveriesPage />));
    await waitFor(() => expect(screen.getByTestId("atr-delivery-7")).toBeInTheDocument());
    expect(screen.getByText("LS.pdf")).toBeInTheDocument();
    expect(screen.getByText("AK111000")).toBeInTheDocument();
  });

  it("assigns the selected deliveries to a container and downloads the label", async () => {
    vi.mocked(atrApi.fetchInputFiles).mockResolvedValue({ configured: false, files: [] });
    const row = {
      compartment: "CCRC", atr_number: null, container_number: null, msn: null,
      status: "draft", created_at: "2026-06-25T10:00:00Z",
    };
    vi.mocked(atrApi.fetchDeliveries).mockResolvedValue([
      { ...row, id: 7, source_filename: "LS7.pdf", ba_auftrag: "1024738" },
      { ...row, id: 8, source_filename: "LS8.pdf", ba_auftrag: "1024739" },
      { ...row, id: 9, source_filename: "LS9.pdf", ba_auftrag: "1024740" },
    ]);
    vi.mocked(atrApi.updateDelivery).mockResolvedValue({} as atrApi.AtrDelivery);
    vi.mocked(atrApi.containerLabelUrl).mockReturnValue("/api/atr/deliveries/container-label?nr=AK222000");
    vi.spyOn(window, "prompt").mockReturnValue(" AK222000 ");
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(wrap(<AtrDeliveriesPage />));
    await waitFor(() => expect(screen.getByTestId("atr-delivery-7")).toBeInTheDocument());
    const button = screen.getByRole("button", { name: i18n.t("atr.deliveries.container_label") });
    expect(button).toBeDisabled();

    fireEvent.click(screen.getByTestId("atr-delivery-select-7"));
    fireEvent.click(screen.getByTestId("atr-delivery-select-9"));
    expect(button).toBeEnabled();
    expect(button).toHaveTextContent("(2)");

    fireEvent.click(button);
    await waitFor(() => expect(atrApi.updateDelivery).toHaveBeenCalledTimes(2));
    expect(atrApi.updateDelivery).toHaveBeenCalledWith(7, { container_number: "AK222000" });
    expect(atrApi.updateDelivery).toHaveBeenCalledWith(9, { container_number: "AK222000" });
    expect(atrApi.containerLabelUrl).toHaveBeenCalledWith("AK222000");
    await waitFor(() => expect(button).toBeDisabled());  // selection cleared
  });
});
