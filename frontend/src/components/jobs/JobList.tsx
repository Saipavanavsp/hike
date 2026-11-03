import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { JobListItem } from "@/api/types";
import { MatchPill } from "@/components/ui/Badges";
import { CompanyLogo, RelativeTime } from "@/components/ui/Misc";
import { formatSalaryRange } from "@/lib/format";

// Tailwind needs complete class names in source, so both variants are spelled out.
const COLS = {
  plain:
    "md:grid md:grid-cols-[36px_minmax(0,2.4fr)_minmax(0,1.4fr)_minmax(0,1fr)_130px_72px_56px] md:items-center md:gap-4",
  action:
    "md:grid md:grid-cols-[36px_minmax(0,2.4fr)_minmax(0,1.4fr)_minmax(0,1fr)_130px_72px_56px_32px] md:items-center md:gap-4",
};

export function JobListHeader({ withAction = false }: { withAction?: boolean }) {
  return (
    <div
      className={`hidden h-10 rounded-t-lg border-b border-border bg-surface/60 px-4 text-2xs font-semibold uppercase tracking-wider text-ink-secondary ${withAction ? COLS.action : COLS.plain}`}
      aria-hidden
    >
      <span />
      <span>Role</span>
      <span>Company</span>
      <span>Location</span>
      <span>Salary</span>
      <span>Posted</span>
      <span className="text-right">Match</span>
      {withAction && <span />}
    </div>
  );
}

export function JobRow({ job, action }: { job: JobListItem; action?: ReactNode }) {
  return (
    <li className="group relative border-b border-border transition-colors last:rounded-b-lg last:border-b-0 hover:bg-surface/60">
      <div
        className={`flex gap-3 px-4 py-3 md:h-[60px] md:py-0 ${action ? COLS.action : COLS.plain}`}
      >
        <CompanyLogo name={job.company.name} size={36} />
        {/* Mobile: two lines. Desktop: one grid row. */}
        <div className="min-w-0 flex-1 md:contents">
          <div className="flex min-w-0 items-baseline gap-2 md:block">
            <Link
              to={`/jobs/${job.id}`}
              className="truncate font-semibold text-ink transition-colors after:absolute after:inset-0 hover:text-accent group-hover:text-accent"
            >
              {job.title}
            </Link>
            <span className="truncate text-sm text-ink-secondary md:hidden">
              {job.company.name}
            </span>
          </div>
          <span className="hidden truncate text-ink-secondary md:block">{job.company.name}</span>
          <div className="mt-0.5 flex items-center gap-2 text-sm text-ink-secondary md:contents">
            <span className="truncate">{job.location}</span>
            <span className="md:hidden" aria-hidden>
              ·
            </span>
            <span className="text-xs font-medium text-ink tabular md:text-sm">
              {formatSalaryRange(job.salary_min, job.salary_max)}
            </span>
            <RelativeTime
              iso={job.posted_at}
              className="hidden text-xs text-ink-secondary md:inline md:text-sm"
            />
            <span className="ml-auto md:ml-0 md:text-right">
              <MatchPill score={job.match_score} />
            </span>
          </div>
        </div>
        {action && <div className="relative z-10 self-center">{action}</div>}
      </div>
    </li>
  );
}

export function JobList({
  jobs,
  renderAction,
}: {
  jobs: JobListItem[];
  renderAction?: (job: JobListItem) => ReactNode;
}) {
  return (
    <ul aria-label="Jobs">
      {jobs.map((j) => (
        <JobRow key={j.id} job={j} action={renderAction?.(j)} />
      ))}
    </ul>
  );
}
