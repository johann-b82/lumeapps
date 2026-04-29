import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { Textarea } from "./textarea"

describe("Textarea", () => {
  it("renders with data-slot='textarea'", () => {
    render(<Textarea aria-label="notes" />)
    expect(screen.getByLabelText("notes")).toHaveAttribute(
      "data-slot",
      "textarea",
    )
  })

  it("defaults to rows=3", () => {
    render(<Textarea aria-label="notes" />)
    expect(screen.getByLabelText("notes")).toHaveAttribute("rows", "3")
  })

  it("respects explicit rows prop", () => {
    render(<Textarea aria-label="notes" rows={7} />)
    expect(screen.getByLabelText("notes")).toHaveAttribute("rows", "7")
  })

  it("applies disabled chain when disabled", () => {
    render(<Textarea aria-label="notes" disabled />)
    const el = screen.getByLabelText("notes")
    expect(el).toBeDisabled()
    expect(el.className).toMatch(/disabled:opacity-50/)
  })

  it("applies invalid chain when aria-invalid", () => {
    render(<Textarea aria-label="notes" aria-invalid />)
    expect(screen.getByLabelText("notes").className).toMatch(
      /aria-invalid:border-destructive/,
    )
  })

  it("merges caller className last (tailwind-merge)", () => {
    render(<Textarea aria-label="notes" className="min-h-32" />)
    expect(screen.getByLabelText("notes").className).toMatch(/min-h-32/)
  })
})
