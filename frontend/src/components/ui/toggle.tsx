import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

export interface ToggleSegment<T extends string> {
  value: T;
  label?: string;
  icon?: ReactNode;
}

export interface ToggleProps<T extends string> {
  // Exactly 2 segments enforced at type + runtime level (D-03)
  segments: readonly [ToggleSegment<T>, ToggleSegment<T>];
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
  "aria-label"?: string;
  title?: string;
  className?: string;
  /**
   * Opt-in surface variant.
   * - "default": bg-background + border-primary (legacy — chart toggles, SubHeader pill)
   * - "muted": bg-muted + border-transparent with hover tint (NavBar cluster parity with UserMenu)
   */
  variant?: "default" | "muted";
}

function usePrefersReducedMotion(): boolean {
  const [reducedMotion, setReducedMotion] = useState<boolean>(() =>
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);
  return reducedMotion;
}

function Toggle<T extends string>({
  segments,
  value,
  onChange,
  disabled = false,
  "aria-label": ariaLabel,
  title,
  className: extraClassName,
  variant = "default",
}: ToggleProps<T>) {
  // Runtime assert — complements the type-level 2-tuple constraint (D-03).
  if (segments.length !== 2) {
    throw new Error(
      "Toggle requires exactly 2 segments; use SegmentedControl for 3+ options.",
    );
  }

  const reducedMotion = usePrefersReducedMotion();
  const buttonRefs = useRef<Array<HTMLButtonElement | null>>([null, null]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [indicatorStyle, setIndicatorStyle] = useState<{ width: number; offset: number } | null>(null);

  const foundIndex = segments.findIndex((s) => s.value === value);
  const activeIndex = foundIndex === -1 ? 0 : foundIndex;

  useLayoutEffect(() => {
    const btn = buttonRefs.current[activeIndex];
    const container = containerRef.current;
    if (!btn || !container) return;
    const update = () => {
      setIndicatorStyle({ width: btn.offsetWidth, offset: btn.offsetLeft });
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(btn);
    ro.observe(container);
    return () => ro.disconnect();
  }, [activeIndex, segments]);

  function handleKey(idx: number, e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      const next = idx === 0 ? 1 : 0;
      onChange(segments[next].value);
      buttonRefs.current[next]?.focus();
    } else if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      const next = idx === 1 ? 0 : 1;
      onChange(segments[next].value);
      buttonRefs.current[next]?.focus();
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onChange(segments[idx].value);
    }
  }

  const containerSurface =
    variant === "muted"
      ? "bg-muted border-transparent hover:bg-accent/20 transition-colors"
      : "bg-background border-primary";
  const containerClassName = `relative inline-flex items-center ${containerSurface} border rounded-full p-1 gap-0${disabled ? " opacity-50 pointer-events-none" : ""}${extraClassName ? ` ${extraClassName}` : ""}`;

  return (
    <div
      ref={containerRef}
      role="radiogroup"
      aria-label={ariaLabel}
      aria-disabled={disabled ? "true" : undefined}
      title={title}
      className={containerClassName}
    >
      <span
        aria-hidden="true"
        className={`absolute top-1 left-0 h-6 rounded-full ${variant === "muted" ? "bg-background shadow-sm" : "bg-primary"}`}
        style={{
          width: indicatorStyle ? `${indicatorStyle.width}px` : `calc(50% - 0.25rem)`,
          transform: `translateX(${indicatorStyle ? indicatorStyle.offset : activeIndex === 0 ? 4 : 0}px)`,
          transition: reducedMotion ? "none" : "transform 180ms ease-out, width 180ms ease-out",
        }}
      />
      {segments.map((segment, i) => {
        if (segment.icon === undefined && segment.label === undefined) {
          throw new Error(
            "Toggle segment requires at least one of `icon` or `label`.",
          );
        }
        const isActive = i === activeIndex;
        // Focus ring: Path A (A11Y-02, Phase 59-02). `focus-visible:z-20` keeps the
        // ring above the animated indicator (which uses `bg-primary` at `z` default).
        // Border swap (used by Button/Input/Textarea/Select) is omitted because the
        // Toggle container — not the segment button — owns the border.
        return (
          <button
            key={segment.value}
            ref={(el) => {
              buttonRefs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={isActive}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onChange(segment.value)}
            onKeyDown={(e) => handleKey(i, e)}
            className={
              isActive
                ? `flex-1 relative z-10 rounded-full h-6 px-3 text-sm font-medium ${variant === "muted" ? "text-foreground" : "text-primary-foreground"} inline-flex items-center justify-center gap-2 transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:z-20`
                : "flex-1 relative z-10 rounded-full h-6 px-3 text-sm font-normal text-muted-foreground hover:text-foreground inline-flex items-center justify-center gap-2 transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:z-20"
            }
          >
            {segment.icon}
            {segment.label}
          </button>
        );
      })}
    </div>
  );
}

export { Toggle };
