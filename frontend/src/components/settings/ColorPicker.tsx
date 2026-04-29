import type { ReactNode } from "react";
import { HexColorPicker } from "react-colorful";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

export interface ColorPickerProps {
  /** Visible label rendered above the row (e.g. "Primary"). */
  label: string;
  /** Current HEX value, format "#rrggbb". NEVER oklch (D-03). */
  value: string;
  /** Fired with a HEX string on any visual or text-input change. */
  onChange: (hex: string) => void;
  /**
   * Optional contrast-badge slot. SettingsPage passes a <ContrastBadge ... />
   * element here for pickers that participate in the 3 BRAND-08 pairs.
   * The picker itself is contrast-agnostic.
   */
  contrastBadge?: ReactNode;
  /** Optional id for the Input; if omitted the hex input gets a deterministic id based on label. */
  id?: string;
}

/**
 * One color-picker row. Renders:
 *   [Label (above)]
 *   [Swatch button] [Hex text input]
 *   [Optional ContrastBadge underneath]
 *
 * The swatch is a Popover trigger; opening it shows a react-colorful
 * HexColorPicker that emits hex on drag. The text input is a parallel
 * editor — both surfaces call the same onChange, so typing a hex
 * updates the swatch and vice versa.
 *
 * Emits HEX only (D-03). The SettingsPage container converts to oklch
 * before writing to the query cache or the PUT payload.
 */
export function ColorPicker({
  label,
  value,
  onChange,
  contrastBadge,
  id,
}: ColorPickerProps) {
  const inputId = id ?? `color-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={inputId} className="text-sm font-medium">
        {label}
      </Label>
      <div className="flex items-center gap-2">
        <Popover>
          <PopoverTrigger
            render={
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label={`Pick ${label} color`}
                className="border-border shadow-sm"
                style={{ backgroundColor: value }}
              />
            }
          />
          <PopoverContent className="w-auto p-3" align="start">
            <HexColorPicker color={value} onChange={onChange} />
          </PopoverContent>
        </Popover>
        <Input
          id={inputId}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="#0066FF"
          className="w-32 font-mono text-sm"
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
        />
      </div>
      {contrastBadge}
    </div>
  );
}
