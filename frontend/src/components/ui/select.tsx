import { Select as SelectPrimitive } from "@base-ui/react/select"
import { ChevronDown } from "lucide-react"

import { cn } from "@/lib/utils"

// Phase 61: The base-ui Select generic tightened in @base-ui/react@1.3.0 —
// Root.Props now requires 1–2 type arguments and its onValueChange is
// (value: Value | null, eventDetails) => void. Our wrapper narrows that
// surface so existing call sites keep passing (v: string) => ... callbacks
// (value can only be null under multiple=false when the selection is
// cleared, which no consumer in this app exercises today — documented
// behaviour is "controlled value always a string"). The non-null boundary
// lives in the wrapper so we don't touch the 5+ consumer files.
type SelectProps<Value = string> = Omit<
  SelectPrimitive.Root.Props<Value>,
  "onValueChange"
> & {
  onValueChange?: (value: Value) => void
}

function Select<Value = string>({
  onValueChange,
  ...props
}: SelectProps<Value>) {
  return (
    <SelectPrimitive.Root
      data-slot="select"
      onValueChange={
        onValueChange
          ? (value) => {
              if (value !== null) onValueChange(value as Value)
            }
          : undefined
      }
      {...props}
    />
  )
}

function SelectValue(props: SelectPrimitive.Value.Props) {
  return <SelectPrimitive.Value data-slot="select-value" {...props} />
}

function SelectTrigger({
  className,
  children,
  ...props
}: SelectPrimitive.Trigger.Props) {
  return (
    <SelectPrimitive.Trigger
      data-slot="select-trigger"
      className={cn(
        "flex h-8 w-full items-center justify-between gap-2 rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors outline-none",
        "placeholder:text-muted-foreground",
        "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
        "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20",
        "md:text-sm dark:bg-input/30",
        "dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40",
        className,
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon className="text-muted-foreground">
        <ChevronDown className="size-4 opacity-50" aria-hidden="true" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  )
}

function SelectContent({
  className,
  children,
  sideOffset = 4,
  ...props
}: SelectPrimitive.Popup.Props & { sideOffset?: number }) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Positioner
        sideOffset={sideOffset}
        className="isolate z-50"
      >
        <SelectPrimitive.Popup
          data-slot="select-content"
          className={cn(
            "z-50 min-w-(--anchor-width) overflow-hidden rounded-lg bg-popover p-1 text-sm text-popover-foreground shadow-md ring-1 ring-foreground/10 outline-hidden",
            className,
          )}
          {...props}
        >
          <SelectPrimitive.List>{children}</SelectPrimitive.List>
        </SelectPrimitive.Popup>
      </SelectPrimitive.Positioner>
    </SelectPrimitive.Portal>
  )
}

function SelectItem({
  className,
  children,
  ...props
}: SelectPrimitive.Item.Props) {
  return (
    <SelectPrimitive.Item
      data-slot="select-item"
      className={cn(
        "relative flex cursor-default select-none items-center rounded-md px-2 py-1 text-sm outline-none",
        "data-[highlighted]:bg-muted data-[highlighted]:text-foreground",
        "data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        className,
      )}
      {...props}
    >
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
    </SelectPrimitive.Item>
  )
}

function SelectGroup(props: SelectPrimitive.Group.Props) {
  return <SelectPrimitive.Group data-slot="select-group" {...props} />
}

function SelectGroupLabel({
  className,
  ...props
}: SelectPrimitive.GroupLabel.Props) {
  return (
    <SelectPrimitive.GroupLabel
      data-slot="select-group-label"
      className={cn("px-2 py-1 text-xs text-muted-foreground", className)}
      {...props}
    />
  )
}

function SelectSeparator({
  className,
  ...props
}: SelectPrimitive.Separator.Props) {
  return (
    <SelectPrimitive.Separator
      data-slot="select-separator"
      className={cn("-mx-1 my-1 h-px bg-border", className)}
      {...props}
    />
  )
}

export {
  Select,
  SelectValue,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectGroup,
  SelectGroupLabel,
  SelectSeparator,
}
