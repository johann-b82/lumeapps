import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Toggle } from "./toggle";

function setupMatchMedia(reduced: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("prefers-reduced-motion") ? reduced : false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

beforeEach(() => setupMatchMedia(false));

describe("Toggle", () => {
  const segs = [
    { value: "a" as const, label: "A" },
    { value: "b" as const, label: "B" },
  ] as const;

  it("renders radiogroup with two radios and correct aria-checked", () => {
    render(<Toggle segments={segs} value="a" onChange={() => {}} aria-label="test" />);
    expect(screen.getByRole("radiogroup")).toBeInTheDocument();
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(2);
    expect(radios[0]).toHaveAttribute("aria-checked", "true");
    expect(radios[1]).toHaveAttribute("aria-checked", "false");
  });

  it("calls onChange when inactive segment is clicked", () => {
    const onChange = vi.fn();
    render(<Toggle segments={segs} value="a" onChange={onChange} aria-label="t" />);
    fireEvent.click(screen.getAllByRole("radio")[1]);
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("ArrowRight moves selection to next segment", () => {
    const onChange = vi.fn();
    render(<Toggle segments={segs} value="a" onChange={onChange} aria-label="t" />);
    fireEvent.keyDown(screen.getAllByRole("radio")[0], { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("ArrowLeft wraps from index 0 to index 1", () => {
    const onChange = vi.fn();
    render(<Toggle segments={segs} value="a" onChange={onChange} aria-label="t" />);
    fireEvent.keyDown(screen.getAllByRole("radio")[0], { key: "ArrowLeft" });
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("Enter reactivates the focused segment", () => {
    const onChange = vi.fn();
    render(<Toggle segments={segs} value="a" onChange={onChange} aria-label="t" />);
    fireEvent.keyDown(screen.getAllByRole("radio")[0], { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith("a");
  });

  it("honors prefers-reduced-motion by disabling indicator transition", () => {
    setupMatchMedia(true);
    const { container } = render(
      <Toggle segments={segs} value="a" onChange={() => {}} aria-label="t" />,
    );
    const indicator = container.querySelector('[aria-hidden="true"]') as HTMLElement;
    expect(indicator).not.toBeNull();
    expect(indicator.style.transition).toBe("none");
  });

  it("throws when not exactly 2 segments", () => {
    // Suppress React's error boundary noise during this test
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => {
      render(
        // @ts-expect-error deliberate bad input for runtime assert
        <Toggle segments={[segs[0]]} value="a" onChange={() => {}} />,
      );
    }).toThrow(/exactly 2 segments/);
    spy.mockRestore();
  });

  it("renders focus-visible ring utility on segment buttons (A11Y-02)", () => {
    render(<Toggle segments={segs} value="a" onChange={() => {}} aria-label="t" />);
    const radios = screen.getAllByRole("radio");
    for (const r of radios) {
      expect(r.className).toContain("focus-visible:ring-3");
      expect(r.className).toContain("focus-visible:ring-ring/50");
      expect(r.className).toContain("outline-none");
      expect(r.className).toContain("focus-visible:z-20");
    }
  });

  it("renders segment icon when provided", () => {
    const segsWithIcon = [
      { value: "x" as const, icon: <svg data-testid="icon-x" /> },
      { value: "y" as const, icon: <svg data-testid="icon-y" /> },
    ] as const;
    render(
      <Toggle segments={segsWithIcon} value="x" onChange={() => {}} aria-label="t" />,
    );
    expect(screen.getByTestId("icon-x")).toBeInTheDocument();
    expect(screen.getByTestId("icon-y")).toBeInTheDocument();
  });
});
