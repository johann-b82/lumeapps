import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n";
import { FairBalloonTable } from "./FairBalloonTable";
import type { FairBalloon } from "@/lib/fairApi";

function b(over: Partial<FairBalloon>): FairBalloon {
  return {
    id: "x",
    number: 1,
    page_no: 1,
    region_x: 0.1,
    region_y: 0.1,
    region_w: 0.1,
    region_h: 0.1,
    tail_x: 0.3,
    tail_y: 0.3,
    value_text: "",
    ...over,
  };
}

const balloons: FairBalloon[] = [
  b({ id: "b2", number: 2, value_text: "M6" }),
  b({ id: "b1", number: 1, value_text: "Ø12,5" }),
];

function renderTable() {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>
        <FairBalloonTable
          projectId="p1"
          projectName="Teil"
          balloons={balloons}
          showPage={false}
          onReocr={() => Promise.resolve(null)}
        />
      </I18nextProvider>
    </QueryClientProvider>,
  );
}

describe("FairBalloonTable", () => {
  it("renders each balloon value as an editable field", () => {
    renderTable();
    expect(screen.getByDisplayValue("Ø12,5")).toBeInTheDocument();
    expect(screen.getByDisplayValue("M6")).toBeInTheDocument();
  });

  it("copies a number-sorted TSV to the clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    renderTable();

    await userEvent.click(screen.getByText(i18n.t("fair.table.copy")));

    expect(writeText).toHaveBeenCalledOnce();
    const tsv = writeText.mock.calls[0][0] as string;
    const lines = tsv.split("\r\n");
    expect(lines[1]).toBe("1\tØ12,5");
    expect(lines[2]).toBe("2\tM6");
  });
});
