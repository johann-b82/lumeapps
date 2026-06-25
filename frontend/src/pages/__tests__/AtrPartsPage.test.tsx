import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import { describe, it, expect, vi, beforeEach } from "vitest";
import i18n from "@/i18n";
import { AtrPartsPage } from "../AtrPartsPage";
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

describe("AtrPartsPage", () => {
  beforeEach(() => vi.resetAllMocks());

  it("renders catalog rows with source file", async () => {
    vi.mocked(atrApi.fetchAtrParts).mockResolvedValue([{
      id: 1, part_number: "VR11S 1010 016 000", part_number_norm: "111010016000",
      supplier_article_code: "6060", part_name: "CARPET EMERGENCY EXIT HATCH",
      drawing_number_issue: "VR11S 1010-10/D", default_weight_kg: "0.413", qty: 1,
      category: "CARPET", po_pos: null, source_filename: "demo.xlsx",
      imported_at: "2026-06-25T00:00:00Z", updated_at: "2026-06-25T00:00:00Z",
    }]);
    render(wrap(<AtrPartsPage />));
    await waitFor(() => expect(screen.getByTestId("atr-part-1")).toBeInTheDocument());
    expect(screen.getByText("demo.xlsx")).toBeInTheDocument();
  });
});
