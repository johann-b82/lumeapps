interface SegmentedControlProps<T extends string> {
  segments: Array<{ value: T; label: string }>;
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
  "aria-label"?: string;
  title?: string;
  className?: string;
}

function SegmentedControl<T extends string>({
  segments,
  value,
  onChange,
  disabled = false,
  "aria-label": ariaLabel,
  title,
  className: extraClassName,
}: SegmentedControlProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      aria-disabled={disabled ? "true" : undefined}
      title={title}
      className={`inline-flex items-center bg-background border border-primary rounded-full p-1 gap-0${disabled ? " opacity-50 pointer-events-none" : ""}${extraClassName ? ` ${extraClassName}` : ""}`}
    >
      {segments.map((segment) => {
        const isActive = segment.value === value;
        return (
          <button
            key={segment.value}
            type="button"
            role="radio"
            aria-checked={isActive}
            onClick={() => onChange(segment.value)}
            className={
              isActive
                ? "bg-primary text-primary-foreground text-sm font-medium rounded-full px-3 h-6 transition-colors"
                : "transparent text-muted-foreground text-sm font-normal rounded-full px-3 h-6 hover:text-foreground transition-colors"
            }
          >
            {segment.label}
          </button>
        );
      })}
    </div>
  );
}

export { SegmentedControl };
