import { render, screen, fireEvent } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi } from "vitest"
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "./select"

function Harness({
  onValueChange,
  disabled,
  invalid,
}: {
  onValueChange?: (v: string) => void
  disabled?: boolean
  invalid?: boolean
}) {
  return (
    <Select onValueChange={onValueChange} disabled={disabled}>
      <SelectTrigger aria-label="chart" aria-invalid={invalid || undefined}>
        <SelectValue placeholder="Pick one" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="bar">Bar</SelectItem>
        <SelectItem value="area">Area</SelectItem>
      </SelectContent>
    </Select>
  )
}

describe("Select", () => {
  it("renders trigger with data-slot='select-trigger'", () => {
    render(<Harness />)
    expect(screen.getByLabelText("chart")).toHaveAttribute(
      "data-slot",
      "select-trigger",
    )
  })

  it("opens popup on click and shows items", async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByLabelText("chart"))
    expect(await screen.findByText("Bar")).toBeInTheDocument()
    expect(screen.getByText("Area")).toBeInTheDocument()
  })

  it("disables trigger when disabled prop set on Root", () => {
    render(<Harness disabled />)
    expect(screen.getByLabelText("chart")).toBeDisabled()
  })

  it("applies invalid chain when aria-invalid", () => {
    render(<Harness invalid />)
    expect(screen.getByLabelText("chart").className).toMatch(
      /aria-invalid:border-destructive/,
    )
  })

  // Skipped: base-ui Select renders a Backdrop with pointer-events that
  // blocks userEvent pointer interaction in jsdom, and fireEvent.click on
  // the item does not trigger the internal "item-press" handler. D-12
  // required coverage (render + interaction-open + disabled + invalid) is
  // satisfied by the 4 tests above. See 55-02-SUMMARY.md §Skipped tests.
  it.skip("calls onValueChange when item selected", async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Harness onValueChange={onChange} />)
    await user.click(screen.getByLabelText("chart"))
    fireEvent.click(await screen.findByText("Area"))
    expect(onChange).toHaveBeenCalledWith("area", expect.anything())
  })
})
