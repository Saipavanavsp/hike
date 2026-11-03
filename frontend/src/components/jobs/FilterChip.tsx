import { ChevronDown, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { icon } from "@/components/ui/icon";
import { cn } from "@/lib/cn";

export interface ChipOption {
  value: string;
  label: string;
}

interface FilterChipProps {
  label: string;
  options: ChipOption[];
  selected: string[];
  onChange: (values: string[]) => void;
  multiple?: boolean;
}

/** "Location: Pune, Remote" chip with a popover of checkboxes (or radios when single). */
export function FilterChip({
  label,
  options,
  selected,
  onChange,
  multiple = true,
}: FilterChipProps) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const active = selected.length > 0;
  const summary = options
    .filter((o) => selected.includes(o.value))
    .map((o) => o.label)
    .join(", ");

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function toggle(value: string) {
    if (!multiple) {
      onChange(selected[0] === value ? [] : [value]);
      setOpen(false);
      return;
    }
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]);
  }

  return (
    <div ref={root} className="relative">
      <div
        className={cn(
          "inline-flex h-8 items-center overflow-hidden rounded-full border text-sm shadow-xs transition-colors",
          active
            ? "border-accent/40 bg-accent-tint text-accent"
            : "border-border bg-bg text-ink hover:border-border-strong hover:bg-surface",
        )}
      >
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((o) => !o)}
          className="inline-flex h-full items-center gap-1.5 pl-3.5 pr-3"
        >
          <span className={cn(active && "font-medium")}>{label}</span>
          {active && <span className="max-w-[160px] truncate">: {summary}</span>}
          {!active && <ChevronDown {...icon} size={14} className="text-ink-muted" />}
        </button>
        {active && (
          <button
            type="button"
            aria-label={`Clear ${label} filter`}
            onClick={() => onChange([])}
            className="inline-flex h-full items-center border-l border-accent/25 pl-2 pr-2.5 transition-colors hover:bg-accent/10"
          >
            <X {...icon} size={14} />
          </button>
        )}
      </div>
      {open && (
        <div
          id={panelId}
          role="group"
          aria-label={`${label} options`}
          className="absolute left-0 z-30 mt-2 min-w-[200px] animate-scale-in rounded-lg border border-border bg-bg p-1 shadow-overlay"
        >
          {options.map((o) => (
            <label
              key={o.value}
              className="flex h-9 cursor-pointer items-center gap-2.5 rounded-md px-3 text-sm hover:bg-surface"
            >
              <input
                type={multiple ? "checkbox" : "radio"}
                name={multiple ? undefined : panelId}
                checked={selected.includes(o.value)}
                onChange={() => toggle(o.value)}
                className="h-4 w-4 accent-[rgb(var(--accent))]"
              />
              {o.label}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
