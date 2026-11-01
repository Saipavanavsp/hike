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
          "inline-flex h-7 items-center rounded border text-sm",
          active ? "border-accent bg-accent-tint text-accent" : "border-border bg-bg text-ink",
        )}
      >
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((o) => !o)}
          className="inline-flex h-full items-center gap-1 pl-2.5 pr-2"
        >
          <span className={cn(active && "font-medium")}>{label}</span>
          {active && <span className="max-w-[160px] truncate">: {summary}</span>}
          {!active && <ChevronDown {...icon} size={14} />}
        </button>
        {active && (
          <button
            type="button"
            aria-label={`Clear ${label} filter`}
            onClick={() => onChange([])}
            className="inline-flex h-full items-center border-l border-accent/30 px-1.5 hover:bg-accent/10"
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
          className="absolute left-0 z-30 mt-1 min-w-[180px] rounded border border-border bg-bg py-1 shadow-overlay"
        >
          {options.map((o) => (
            <label
              key={o.value}
              className="flex h-8 cursor-pointer items-center gap-2 px-3 text-sm hover:bg-surface"
            >
              <input
                type={multiple ? "checkbox" : "radio"}
                name={multiple ? undefined : panelId}
                checked={selected.includes(o.value)}
                onChange={() => toggle(o.value)}
                className="h-4 w-4 accent-accent"
              />
              {o.label}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
