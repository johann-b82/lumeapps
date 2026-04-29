import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi } from "vitest"
import {
  Dropdown,
  DropdownTrigger,
  DropdownContent,
  DropdownItem,
} from "./dropdown"
import { Button } from "./button"

function Harness({
  onEdit,
  onDelete,
  deleteDisabled,
}: {
  onEdit?: () => void
  onDelete?: () => void
  deleteDisabled?: boolean
}) {
  return (
    <Dropdown>
      <DropdownTrigger
        render={<Button size="icon-sm" variant="ghost" aria-label="Actions" />}
      />
      <DropdownContent>
        <DropdownItem onClick={onEdit}>Edit</DropdownItem>
        <DropdownItem
          onClick={onDelete}
          disabled={deleteDisabled}
          className="text-destructive"
        >
          Delete
        </DropdownItem>
      </DropdownContent>
    </Dropdown>
  )
}

describe("Dropdown", () => {
  it("renders trigger via render prop (Button styling)", () => {
    render(<Harness />)
    const trigger = screen.getByLabelText("Actions")
    expect(trigger).toBeInTheDocument()
  })

  it("opens popup on click and shows items", async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByLabelText("Actions"))
    expect(await screen.findByText("Edit")).toBeInTheDocument()
    expect(screen.getByText("Delete")).toBeInTheDocument()
  })

  it("fires onClick when item clicked", async () => {
    const user = userEvent.setup()
    const onEdit = vi.fn()
    render(<Harness onEdit={onEdit} />)
    await user.click(screen.getByLabelText("Actions"))
    await user.click(await screen.findByText("Edit"))
    expect(onEdit).toHaveBeenCalledTimes(1)
  })

  it("applies destructive class on Delete item", async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByLabelText("Actions"))
    const deleteItem = await screen.findByText("Delete")
    expect(deleteItem.className).toMatch(/text-destructive/)
  })

  it("does not fire onClick when item disabled", async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()
    render(<Harness onDelete={onDelete} deleteDisabled />)
    await user.click(screen.getByLabelText("Actions"))
    const deleteItem = await screen.findByText("Delete")
    await user.click(deleteItem).catch(() => {})
    expect(onDelete).not.toHaveBeenCalled()
  })
})
