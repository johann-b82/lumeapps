import { useId, useRef, useState, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";

import { signageKeys } from "@/lib/queryKeys";
import { signageApi } from "@/signage/lib/signageApi";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export interface TagPickerProps {
  /** Tag names already selected (controlled). */
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
  ariaLabel?: string;
}

/**
 * Token-chip autocomplete for signage tags. Pure presentational over a
 * `string[]` — caller is responsible for resolving names → ids on submit.
 *
 * Keyboard contract (D-14):
 *   Enter / comma  → commit current input as a new chip
 *   Backspace      → remove last chip when input is empty
 *   Escape         → close suggestion dropdown
 */
export function TagPicker({
  value,
  onChange,
  placeholder,
  disabled,
  ariaLabel,
}: TagPickerProps) {
  const { t } = useTranslation();
  const [inputValue, setInputValue] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const listboxId = useId();

  // D-15: fetch the tag list once per session; filter client-side.
  const { data: allTags = [] } = useQuery({
    queryKey: signageKeys.tags(),
    queryFn: signageApi.listTags,
    staleTime: Infinity,
  });

  const trimmed = inputValue.trim();
  const existingNames = new Set(allTags.map((tag) => tag.name.toLowerCase()));
  const suggestions = allTags
    .filter(
      (tag) =>
        tag.name.toLowerCase().includes(trimmed.toLowerCase()) &&
        !value.includes(tag.name),
    )
    .slice(0, 8);
  const showCreate =
    trimmed.length > 0 &&
    !existingNames.has(trimmed.toLowerCase()) &&
    !value.includes(trimmed);

  function commit(tag: string) {
    const next = tag.trim();
    if (!next || value.includes(next)) return;
    onChange([...value, next]);
    setInputValue("");
    setIsOpen(false);
  }

  function remove(tag: string) {
    onChange(value.filter((v) => v !== tag));
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      if (trimmed) commit(trimmed);
      return;
    }
    if (event.key === "Backspace" && inputValue === "" && value.length > 0) {
      event.preventDefault();
      remove(value[value.length - 1]);
      return;
    }
    if (event.key === "Escape") {
      setIsOpen(false);
    }
  }

  const resolvedPlaceholder =
    placeholder ?? t("signage.admin.tag_picker.placeholder");

  return (
    <div className="relative">
      <div
        className="border border-input rounded-lg px-2.5 py-1 flex flex-wrap items-center gap-1 min-h-8 h-8 cursor-text bg-background text-sm"
        onClick={() => inputRef.current?.focus()}
        role="combobox"
        aria-expanded={isOpen}
        aria-controls={listboxId}
        aria-label={ariaLabel}
      >
        {value.map((tag) => (
          <Badge key={tag} variant="secondary" className="gap-1 pr-1">
            <span>{tag}</span>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={(event) => {
                event.stopPropagation();
                remove(tag);
              }}
              aria-label={`Remove ${tag}`}
              disabled={disabled}
            >
              <X className="w-3 h-3" />
            </Button>
          </Badge>
        ))}
        <Input
          ref={inputRef}
          value={inputValue}
          onChange={(event) => {
            setInputValue(event.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onBlur={() => setTimeout(() => setIsOpen(false), 150)}
          onKeyDown={handleKeyDown}
          placeholder={value.length === 0 ? resolvedPlaceholder : ""}
          className="flex-1 min-w-[100px] border-0 bg-transparent px-0 py-0 h-auto focus-visible:ring-0 focus-visible:border-0"
          disabled={disabled}
        />
      </div>

      {isOpen && (suggestions.length > 0 || showCreate) && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-50 mt-1 w-full min-w-[200px] bg-popover border border-border rounded-md shadow-md py-1 max-h-60 overflow-auto"
        >
          {suggestions.map((tag) => (
            <li
              key={tag.id}
              role="option"
              aria-selected={false}
              className="text-sm px-3 py-2 hover:bg-muted cursor-pointer"
              onMouseDown={(event) => {
                event.preventDefault();
                commit(tag.name);
              }}
            >
              {tag.name}
            </li>
          ))}
          {showCreate && (
            <li
              role="option"
              aria-selected={false}
              className="text-sm px-3 py-2 text-primary hover:bg-muted cursor-pointer"
              onMouseDown={(event) => {
                event.preventDefault();
                commit(trimmed);
              }}
            >
              {t("signage.admin.tag_picker.create", { tag: trimmed })}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
