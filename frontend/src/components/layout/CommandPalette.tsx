import { ArrowRight, CornerDownLeft, Search } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import type { Role } from "@/api/types";
import { icon } from "@/components/ui/icon";
import { cn } from "@/lib/cn";
import { NAV } from "./nav";

interface Command {
  id: string;
  label: ReactNode;
  hint: string;
  icon: typeof Search;
  run: () => void;
}

/** Keyboard-first page switcher (Ctrl/Cmd+K). Seekers can also start a job search from it. */
export function CommandPalette({
  role,
  open,
  onClose,
}: {
  role: Role;
  open: boolean;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const listId = useId();

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    const previous = document.activeElement as HTMLElement | null;
    requestAnimationFrame(() => input.current?.focus());
    return () => previous?.focus();
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const q = query.trim();
    const go = (to: string) => () => {
      onClose();
      navigate(to);
    };
    const pages = NAV[role]
      .filter((i) => !q || i.label.toLowerCase().includes(q.toLowerCase()))
      .map<Command>((i) => ({
        id: i.to,
        label: i.label,
        hint: i.group,
        icon: i.icon,
        run: go(i.to),
      }));
    if (role === "seeker" && q) {
      pages.unshift({
        id: "search-jobs",
        label: (
          <>
            Search jobs for <span className="font-semibold">“{q}”</span>
          </>
        ),
        hint: "Jobs",
        icon: Search,
        run: go(`/jobs?${new URLSearchParams({ q })}`),
      });
    }
    return pages;
  }, [query, role, navigate, onClose]);

  useEffect(() => setActive(0), [query]);

  if (!open) return null;

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => (commands.length ? (a + 1) % commands.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (commands.length ? (a - 1 + commands.length) % commands.length : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      commands[active]?.run();
    } else if (e.key === "Tab") {
      e.preventDefault(); // focus stays in the palette
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex animate-fade-in items-start justify-center bg-[rgb(var(--shadow)/0.45)] p-4 pt-[12vh] backdrop-blur-[2px]"
      onMouseDown={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command menu"
        className="w-full max-w-lg animate-scale-in overflow-hidden rounded-xl border border-border bg-bg shadow-overlay"
        onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={onKeyDown}
      >
        <div className="flex items-center gap-2.5 border-b border-border px-4">
          <Search {...icon} className="text-ink-muted" />
          <input
            ref={input}
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={commands[active] ? `${listId}-${active}` : undefined}
            aria-label="Go to a page"
            placeholder={role === "seeker" ? "Go to a page or search jobs…" : "Go to a page…"}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="h-12 flex-1 bg-transparent text-sm text-ink placeholder:text-ink-muted focus:outline-none focus-visible:ring-0"
          />
          <kbd className="rounded border border-border bg-surface px-1.5 font-mono text-2xs text-ink-secondary">
            Esc
          </kbd>
        </div>
        <ul
          id={listId}
          role="listbox"
          aria-label="Pages"
          className="max-h-[320px] overflow-y-auto p-1.5"
        >
          {commands.length === 0 && (
            <li className="px-3 py-8 text-center text-sm text-ink-secondary">No matching pages.</li>
          )}
          {commands.map((c, i) => (
            <li
              key={c.id}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseMove={() => setActive(i)}
              onClick={c.run}
              className={cn(
                "flex h-10 cursor-pointer items-center gap-3 rounded-md px-3 text-sm",
                i === active ? "bg-surface text-ink" : "text-ink-secondary",
              )}
            >
              <c.icon {...icon} className={i === active ? "text-accent" : "text-ink-muted"} />
              <span className="flex-1 truncate text-ink">{c.label}</span>
              <span className="text-xs text-ink-muted">{c.hint}</span>
              {i === active ? (
                <CornerDownLeft {...icon} size={14} className="text-ink-muted" />
              ) : (
                <ArrowRight {...icon} size={14} className="invisible" />
              )}
            </li>
          ))}
        </ul>
        <div className="flex items-center gap-4 border-t border-border bg-surface/60 px-4 py-2 text-xs text-ink-secondary">
          <span>
            <kbd className="font-mono">↑</kbd> <kbd className="font-mono">↓</kbd> to move
          </span>
          <span>
            <kbd className="font-mono">Enter</kbd> to open
          </span>
        </div>
      </div>
    </div>,
    document.body,
  );
}
