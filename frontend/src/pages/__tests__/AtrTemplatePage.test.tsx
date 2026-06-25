// frontend/src/pages/__tests__/AtrTemplatePage.test.tsx
import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import { describe, it, expect, vi, beforeEach } from "vitest";
import i18n from "@/i18n";
import { AtrTemplatePage } from "../AtrTemplatePage";
import * as atrApi from "@/lib/atrApi";

vi.mock("@/lib/atrApi");

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>{ui}</I18nextProvider>
    </QueryClientProvider>
  );
}

describe("AtrTemplatePage", () => {
  beforeEach(() => vi.resetAllMocks());

  it("renders header defaults from the template", async () => {
    vi.mocked(atrApi.fetchAtrTemplate).mockResolvedValue({
      id: 1, customer: "Diehl Aviation Laupheim GmbH", ac_programme: "A350 XWB",
      work_package: null, purchaser_spec: null, atp: null, supplier_spec: null,
      reference_no: null, supplier: null, customer_spec: "C9312", nscm_code: "C9312",
      ata_chapter: "25", weighing_equipment: "Plattenwaage PW015",
      qa_signer_default: "Cordula Kesseler i.A.", structure_filename: null,
      has_structure: false, updated_at: "2026-06-25T00:00:00Z",
    });
    render(wrap(<AtrTemplatePage />));
    await waitFor(() =>
      expect(screen.getByDisplayValue("Diehl Aviation Laupheim GmbH")).toBeInTheDocument());
    expect(screen.getByDisplayValue("Plattenwaage PW015")).toBeInTheDocument();
  });
});
