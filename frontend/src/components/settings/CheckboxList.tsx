import { useTranslation } from "react-i18next";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export interface CheckboxOption {
  value: string;
  label: string;
}

interface CheckboxListProps {
  /** Unique id prefix for accessibility (e.g. "sick-leave") */
  id: string;
  /** Field label displayed above the list */
  label: string;
  /** Available options to display as checkboxes */
  options: CheckboxOption[];
  /** Currently selected values */
  selected: string[];
  /** Called with the full new array when any checkbox is toggled */
  onChange: (selected: string[]) => void;
  /** Disables all checkboxes */
  disabled?: boolean;
  /** Shows loading text inside the container */
  loading?: boolean;
  /** Hint text below the container (e.g. "configure credentials") */
  hint?: string | null;
}

export function CheckboxList({
  id,
  label,
  options,
  selected,
  onChange,
  disabled = false,
  loading = false,
  hint,
}: CheckboxListProps) {
  const { t } = useTranslation();

  const handleToggle = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  return (
    <div className="flex flex-col gap-2 max-w-md">
      <Label className="text-sm font-medium">{label}</Label>
      <div
        className={cn(
          "max-h-[200px] overflow-y-auto rounded-md border border-input bg-transparent px-1 py-1 text-sm shadow-xs",
          disabled && "opacity-50 cursor-not-allowed"
        )}
      >
        {loading ? (
          <p className="px-2 py-1.5 text-muted-foreground">{t("settings.personio.loading")}</p>
        ) : options.length === 0 ? (
          <p className="px-2 py-1.5 text-muted-foreground">{t("settings.personio.no_options")}</p>
        ) : (
          options.map((opt) => (
            <label
              key={opt.value}
              htmlFor={`${id}-${opt.value}`}
              className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-accent/10 cursor-pointer"
            >
              <Checkbox
                id={`${id}-${opt.value}`}
                checked={selected.includes(opt.value)}
                onCheckedChange={() => handleToggle(opt.value)}
                disabled={disabled}
              />
              <span className="text-sm">{opt.label}</span>
            </label>
          ))
        )}
      </div>
      {hint && (
        <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}
