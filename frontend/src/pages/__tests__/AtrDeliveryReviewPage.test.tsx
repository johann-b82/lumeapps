// frontend/src/pages/__tests__/AtrDeliveryReviewPage.test.tsx
import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { describe, it, expect, vi, beforeEach } from "vitest";
import i18n from "@/i18n";
import { AtrDeliveryReviewPage } from "../AtrDeliveryReviewPage";
import * as atrApi from "@/lib/atrApi";

vi.mock("@/lib/atrApi");

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const mem = memoryLocation({ path: "/atr/deliveries/7" });
  return (
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}><Router hook={mem.hook}>{ui}</Router></I18nextProvider>
    </QueryClientProvider>
  );
}

describe("AtrDeliveryReviewPage", () => {
  beforeEach(() => vi.resetAllMocks());
  it("renders header + items, flags unmatched", async () => {
    vi.mocked(atrApi.fetchDelivery).mockResolvedValue({
      id: 7, source_filename: "LS.pdf", lieferschein_nr: "20189798", datum: "2026-06-08",
      ba_auftrag: "1024738", po_number: "4501119979", ac_programme: "A350",
      programme_reason: null,
      compartment: "CCRC", msn: "830", bed_config: "6", set_title: "SET 6 BED CCRC",
      atr_number: null, container_number: null, weighing_date: "2026-06-25",
      testing_date: "2026-06-25", qa_signer: "Cordula Kesseler i.A.",
      max_guaranteed_weight_kg: null, status: "draft",
      created_at: "2026-06-25T10:00:00Z", updated_at: "2026-06-25T10:00:00Z",
      items: [
        { id: 1, pos: 1, supplier_article_code: "6060", part_number: "VR11S 1010 016 000",
          part_number_norm: "111010016000", matched_part_id: 5, part_name: "CARPET EMERGENCY EXIT HATCH",
          drawing_number_issue: "VR11S 1010-10/D", category: "CARPET", qty: 1,
          weight_kg: "0.413", po_pos: "050", match_status: "matched", row_order: 1,
          serial_numbers: null },
        { id: 2, pos: 2, supplier_article_code: "9999", part_number: "VR11S 9999 999 999",
          part_number_norm: "999999999", matched_part_id: null, part_name: "UNKNOWN",
          drawing_number_issue: null, category: null, qty: 1,
          weight_kg: null, po_pos: null, match_status: "unmatched", row_order: 2,
          serial_numbers: null },
      ],
    });
    render(wrap(<AtrDeliveryReviewPage />));
    await waitFor(() => expect(screen.getByTestId("atr-item-1")).toBeInTheDocument());
    expect(screen.getByDisplayValue("SET 6 BED CCRC")).toBeInTheDocument();
    expect(screen.getByTestId("atr-item-2").className).toContain("bg-red-100");
  });
});
