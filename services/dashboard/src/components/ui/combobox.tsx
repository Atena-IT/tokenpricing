import { Check, ChevronsUpDown, SearchX } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";

import { cn } from "../../lib/utils";

export interface ComboboxOption {
  value: string;
  label: string;
  hint?: string;
}

const VISIBLE_LIMIT = 60;

/**
 * Searchable single-select for large option sets (the model catalog has 3k+
 * entries, far beyond what a plain select can handle comfortably).
 */
export function Combobox({
  options,
  value,
  onChange,
  placeholder = "Select…",
  searchPlaceholder = "Search…",
  className,
}: {
  options: ComboboxOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlighted, setHighlighted] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const listboxId = useId();

  const selected = useMemo(() => options.find((option) => option.value === value), [options, value]);

  const filtered = useMemo(() => {
    const lowered = query.trim().toLowerCase();
    const matches = lowered
      ? options.filter(
          (option) =>
            option.label.toLowerCase().includes(lowered) ||
            option.value.toLowerCase().includes(lowered) ||
            option.hint?.toLowerCase().includes(lowered),
        )
      : options;
    return { visible: matches.slice(0, VISIBLE_LIMIT), hidden: Math.max(0, matches.length - VISIBLE_LIMIT) };
  }, [options, query]);

  useEffect(() => {
    if (!open) {
      return;
    }
    searchRef.current?.focus();
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, [open]);

  const select = (option: ComboboxOption) => {
    onChange(option.value);
    setOpen(false);
    setQuery("");
  };

  const onSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlighted((index) => Math.min(index + 1, filtered.visible.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlighted((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const option = filtered.visible[highlighted];
      if (option) {
        select(option);
      }
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        onClick={() => setOpen((current) => !current)}
        className="flex h-9 w-full items-center justify-between gap-2 rounded-md border border-input bg-card px-3 text-sm shadow-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
      >
        <span className={cn("truncate text-left", !selected && "text-muted-foreground")}>
          {selected?.label ?? placeholder}
        </span>
        <ChevronsUpDown className="h-4 w-4 shrink-0 text-muted-foreground" />
      </button>
      {open ? (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md">
          <div className="border-b p-1.5">
            <input
              ref={searchRef}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setHighlighted(0);
              }}
              onKeyDown={onSearchKeyDown}
              placeholder={searchPlaceholder}
              className="h-8 w-full rounded-sm bg-transparent px-2 text-sm outline-none placeholder:text-muted-foreground"
              aria-autocomplete="list"
            />
          </div>
          <ul id={listboxId} role="listbox" className="max-h-72 overflow-y-auto p-1">
            {filtered.visible.map((option, index) => (
              <li
                key={option.value}
                role="option"
                aria-selected={option.value === value}
                onMouseEnter={() => setHighlighted(index)}
                onMouseDown={(event) => {
                  event.preventDefault();
                  select(option);
                }}
                className={cn(
                  "flex cursor-default items-center gap-2 rounded-sm px-2 py-1.5 text-sm",
                  index === highlighted && "bg-accent text-accent-foreground",
                )}
              >
                <Check
                  className={cn("h-4 w-4 shrink-0 text-primary", option.value !== value && "invisible")}
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{option.label}</span>
                  {option.hint ? (
                    <span className="block truncate font-mono text-xs text-muted-foreground">{option.hint}</span>
                  ) : null}
                </span>
              </li>
            ))}
            {filtered.visible.length === 0 ? (
              <li className="flex items-center gap-2 px-2 py-6 text-sm text-muted-foreground">
                <SearchX className="h-4 w-4" />
                No models match “{query}”
              </li>
            ) : null}
            {filtered.hidden > 0 ? (
              <li className="px-2 py-1.5 text-xs text-muted-foreground">
                {filtered.hidden.toLocaleString("en-US")} more — keep typing to narrow down
              </li>
            ) : null}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
