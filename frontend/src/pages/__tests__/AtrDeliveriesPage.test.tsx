// frontend/src/pages/__tests__/AtrDeliveriesPage.test.tsx
import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
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
      compartment: "CCRC", status: "draft", created_at: "2026-06-25T10:00:00Z",
    }]);
    render(wrap(<AtrDeliveriesPage />));
    await waitFor(() => expect(screen.getByTestId("atr-delivery-7")).toBeInTheDocument());
    expect(screen.getByText("LS.pdf")).toBeInTheDocument();
  });
});
