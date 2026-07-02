// frontend/src/pages/__tests__/AtrImportPage.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { describe, it, expect, vi, beforeEach } from "vitest";
import i18n from "@/i18n";
import { AtrImportPage } from "../AtrImportPage";
import * as atrApi from "@/lib/atrApi";

vi.mock("@/lib/atrApi");

describe("AtrImportPage", () => {
  beforeEach(() => vi.resetAllMocks());

  it("shows preview counts and warnings after choosing a file", async () => {
    vi.mocked(atrApi.atrImportPreview).mockResolvedValue([{
      source_filename: "demo.xlsx", header: {}, new_count: 2, updated_count: 0,
      unchanged_count: 0, warnings: ["row 9: unparseable weight"],
      parts: [{
        part_number: "VR11S 1010 016 000", part_number_norm: "111010016000",
        supplier_article_code: "6060", part_name: "CARPET", drawing_number_issue: "X",
        default_weight_kg: "0.413", qty: 1, category: "CARPET", status: "new",
      }],
    }]);
    render(
      <I18nextProvider i18n={i18n}>
        <AtrImportPage />
      </I18nextProvider>,
    );
    const input = screen.getByLabelText(/xlsx/i);
    const file = new File(["x"], "demo.xlsx",
      { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByText(/Preview|Vorschau/));
    await waitFor(() => expect(screen.getByText("demo.xlsx")).toBeInTheDocument());
    expect(screen.getByTestId("atr-warnings")).toHaveTextContent("unparseable weight");
  });
});
