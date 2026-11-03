import { Check, X } from "lucide-react";
import type { JobDetail } from "@/api/types";
import { MatchPill, Tag } from "@/components/ui/Badges";
import { icon } from "@/components/ui/icon";
import { ScoreComponents } from "./ScoreComponents";

function Mark({ ok }: { ok: boolean }) {
  return ok ? (
    <Check {...icon} className="mt-0.5 shrink-0 text-status-green" aria-label="Meets requirement" />
  ) : (
    <X
      {...icon}
      className="mt-0.5 shrink-0 text-status-red"
      aria-label="Does not meet requirement"
    />
  );
}

/** Match breakdown as plain text lines. No charts. */
export function MatchBreakdownPanel({ job }: { job: JobDetail }) {
  const m = job.match;
  if (!m) return null;
  const years = m.experience_years;
  const allMatched = m.skills_missing.length === 0;
  return (
    <div className="space-y-2.5 text-sm" aria-label="Match breakdown">
      <div className="flex items-center justify-between">
        <span className="font-medium">Your match</span>
        <MatchPill score={m.score} />
      </div>
      <div className="flex gap-2">
        <Mark ok={allMatched} />
        <div className="min-w-0">
          <p>
            Skills matched: <span className="tabular">{m.skills_ratio}</span>
          </p>
          {m.skills_missing.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1" aria-label="Missing skills">
              {m.skills_missing.map((s) => (
                <Tag key={s}>{s}</Tag>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="flex gap-2">
        <Mark ok={m.experience_ok} />
        <p>
          Experience:{" "}
          <span className="tabular">{years === null ? "not stated" : `${years} yrs`}</span>{" "}
          <span className="text-ink-secondary">
            (needs {job.experience_min}–{job.experience_max})
          </span>
        </p>
      </div>
      <div className="flex gap-2">
        <Mark ok={m.location_ok} />
        <p>
          Location: {job.location}
          {job.remote_type === "hybrid" && <span className="text-ink-secondary"> (hybrid)</span>}
        </p>
      </div>
      {m.components?.length > 0 && (
        <details className="border-t border-border pt-2">
          <summary className="cursor-pointer text-xs text-accent hover:text-accent-hover">
            How this score is calculated
          </summary>
          <div className="mt-2">
            <ScoreComponents components={m.components} score={m.score} />
            <p className="mt-2 text-xs text-ink-secondary">
              Your name, contact details and college are removed before the text comparison, so they
              never affect the score. Edit your skills or experience on the Resume page if something
              is wrong.
            </p>
          </div>
        </details>
      )}
    </div>
  );
}
