import { X } from "lucide-react";
import { useId, useState } from "react";
import { useSkillSearch } from "@/api/queries";
import { Input } from "@/components/ui/Form";
import { icon } from "@/components/ui/icon";

/** Editable list of skill tags with taxonomy suggestions. */
export function SkillEditor({
  value,
  onChange,
}: {
  value: string[];
  onChange: (skills: string[]) => void;
}) {
  const [text, setText] = useState("");
  const listId = useId();
  const { data: suggestions = [] } = useSkillSearch(text);
  const options = suggestions
    .filter((s) => !value.some((v) => v.toLowerCase() === s.toLowerCase()))
    .slice(0, 6);

  function add(skill: string) {
    const s = skill.trim();
    if (s && !value.some((v) => v.toLowerCase() === s.toLowerCase())) onChange([...value, s]);
    setText("");
  }

  return (
    <div>
      <ul className="mb-2 flex flex-wrap gap-1" aria-label="Skills">
        {value.map((s) => (
          <li
            key={s}
            className="inline-flex h-6 items-center gap-1 rounded-sm border border-border bg-surface pl-2 pr-1 text-xs"
          >
            {s}
            <button
              type="button"
              aria-label={`Remove ${s}`}
              onClick={() => onChange(value.filter((v) => v !== s))}
              className="inline-flex h-4 w-4 items-center justify-center rounded-sm text-ink-secondary hover:bg-border hover:text-ink"
            >
              <X {...icon} size={12} />
            </button>
          </li>
        ))}
        {value.length === 0 && <li className="text-xs text-ink-secondary">No skills yet.</li>}
      </ul>
      <div className="relative max-w-[320px]">
        <Input
          aria-label="Add a skill"
          placeholder="Add a skill and press Enter"
          value={text}
          list={listId}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              // Add exactly what was typed; the API maps aliases ("js", "postgres") to canonical names.
              add(text);
            }
          }}
        />
        <datalist id={listId}>
          {options.map((o) => (
            <option key={o} value={o} />
          ))}
        </datalist>
      </div>
    </div>
  );
}
