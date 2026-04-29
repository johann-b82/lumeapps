import { Menu as MenuPrimitive } from "@base-ui/react/menu"

import { cn } from "@/lib/utils"

function Dropdown(props: MenuPrimitive.Root.Props) {
  return <MenuPrimitive.Root data-slot="dropdown" {...props} />
}

function DropdownTrigger(props: MenuPrimitive.Trigger.Props) {
  return <MenuPrimitive.Trigger data-slot="dropdown-trigger" {...props} />
}

type DropdownContentProps = MenuPrimitive.Popup.Props &
  Pick<MenuPrimitive.Positioner.Props, "align" | "sideOffset">

function DropdownContent({
  className,
  children,
  align = "end",
  sideOffset = 4,
  ...props
}: DropdownContentProps) {
  return (
    <MenuPrimitive.Portal>
      <MenuPrimitive.Positioner
        align={align}
        sideOffset={sideOffset}
        className="isolate z-50"
      >
        <MenuPrimitive.Popup
          data-slot="dropdown-content"
          className={cn(
            "z-50 min-w-[8rem] overflow-hidden rounded-lg bg-popover p-1 text-sm text-popover-foreground shadow-md ring-1 ring-foreground/10 outline-hidden",
            className
          )}
          {...props}
        >
          {children}
        </MenuPrimitive.Popup>
      </MenuPrimitive.Positioner>
    </MenuPrimitive.Portal>
  )
}

function DropdownItem({ className, ...props }: MenuPrimitive.Item.Props) {
  return (
    <MenuPrimitive.Item
      data-slot="dropdown-item"
      className={cn(
        "relative flex cursor-default select-none items-center gap-2 rounded-md px-2 py-1 text-sm outline-none",
        "data-[highlighted]:bg-muted data-[highlighted]:text-foreground",
        "data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        className
      )}
      {...props}
    />
  )
}

function DropdownSeparator({
  className,
  ...props
}: MenuPrimitive.Separator.Props) {
  return (
    <MenuPrimitive.Separator
      data-slot="dropdown-separator"
      className={cn("-mx-1 my-1 h-px bg-border", className)}
      {...props}
    />
  )
}

export {
  Dropdown,
  DropdownTrigger,
  DropdownContent,
  DropdownItem,
  DropdownSeparator,
}
