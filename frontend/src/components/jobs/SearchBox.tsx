import { Search } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { useAutocomplete } from "@/api/queries";
import { icon } from "@/components/ui/icon";
import { cn } from "@/lib/cn";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** Search input with title/skill suggestions (ARIA combobox). */
export function SearchBox({ value, onSearch }: { value: string; onSearch: (q: string) => void }) {
  const [text, setText] = useState(value);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const listId = useId();
  const debounced = useDebounced(text, 150);
  const { data: suggestions = [] } = useAutocomplete(open ? debounced : "");

  useEffect(() => setText(value), [value]);

  function submit(q: string) {
    setText(q);
    setOpen(false);
    setActive(-1);
    onSearch(q.trim());
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" && suggestions.length) {
      e.preventDefault();
      setOpen(true);
      setActive((a) => (a + 1) % suggestions.length);
    } else if (e.key === "ArrowUp" && suggestions.length) {
      e.preventDefault();
      setActive((a) => (a - 1 + suggestions.length) % suggestions.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      submit(active >= 0 && open ? suggestions[active].text : text);
    } else if (e.key === "Escape") {
      setOpen(false);
      setActive(-1);
    }
  }

  const showList = open && text.trim().length > 0 && suggestions.length > 0;

  return (
    <div className="relative flex-1">
      <Search
        {...icon}
        className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-muted"
      />
      <input
        type="search"
        role="combobox"
        aria-label="Search jobs by title, skill or company"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showList && active >= 0 ? `${listId}-${active}` : undefined}
        placeholder="Search by title, skill or company"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
          setActive(-1);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={onKeyDown}
        className="h-11 w-full rounded-lg border border-border bg-bg pl-10 pr-3 text-[15px] text-ink shadow-xs placeholder:text-ink-muted transition-[border-color,box-shadow] hover:border-border-strong focus:border-accent focus:outline-none focus:ring-[3px] focus:ring-accent/20"
      />
      {showList && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-2 w-full animate-scale-in rounded-lg border border-border bg-bg p-1 shadow-overlay"
        >
          {suggestions.map((s, i) => (
            <li
              key={`${s.kind}-${s.text}`}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                submit(s.text);
              }}
              className={cn(
                "flex h-9 cursor-pointer items-center justify-between rounded-md px-3 text-sm",
                i === active ? "bg-surface" : "hover:bg-surface",
              )}
            >
              <span>{s.text}</span>
              <span className="text-xs text-ink-muted">
                {s.kind === "title" ? "Job title" : "Skill"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
