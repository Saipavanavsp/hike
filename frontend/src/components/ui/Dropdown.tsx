import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface DropdownItem {
  label: ReactNode;
  onSelect: () => void;
  danger?: boolean;
  disabled?: boolean;
}

interface DropdownProps {
  trigger: (props: {
    onClick: () => void;
    "aria-expanded": boolean;
    "aria-haspopup": "menu";
  }) => ReactNode;
  items: DropdownItem[];
  align?: "left" | "right";
  header?: ReactNode;
}

/** Menu with click-outside, Escape and arrow-key support. */
export function Dropdown({ trigger, items, align = "right", header }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    if (!open) return;
    itemRefs.current.find((el) => el && !el.disabled)?.focus();
    function onDown(e: MouseEvent) {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  function onKeyDown(e: React.KeyboardEvent) {
    if (!open) return;
    const els = itemRefs.current.filter((el): el is HTMLButtonElement => !!el && !el.disabled);
    const idx = els.indexOf(document.activeElement as HTMLButtonElement);
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      (root.current?.querySelector("[aria-haspopup]") as HTMLElement | null)?.focus();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      els[(idx + 1) % els.length]?.focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      els[(idx - 1 + els.length) % els.length]?.focus();
    }
  }

  return (
    <div ref={root} className="relative" onKeyDown={onKeyDown}>
      {trigger({
        onClick: () => setOpen((o) => !o),
        "aria-expanded": open,
        "aria-haspopup": "menu",
      })}
      {open && (
        <div
          role="menu"
          className={cn(
            "absolute z-40 mt-1 min-w-[180px] rounded border border-border bg-bg py-1 shadow-overlay",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {header && (
            <div className="border-b border-border px-3 pb-2 pt-1 text-xs text-ink-secondary">
              {header}
            </div>
          )}
          {items.map((item, i) => (
            <button
              key={i}
              ref={(el) => (itemRefs.current[i] = el)}
              role="menuitem"
              type="button"
              disabled={item.disabled}
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
              className={cn(
                "flex h-8 w-full items-center gap-2 px-3 text-left text-sm hover:bg-surface focus:bg-surface focus:outline-none disabled:opacity-50",
                item.danger ? "text-status-red" : "text-ink",
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
