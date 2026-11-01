import type { RecruiterApplication } from "@/api/types";
import { MatchPill, StatusBadge, Tag } from "@/components/ui/Badges";
import { EmptyState, RelativeTime } from "@/components/ui/Misc";
import { Table, TD, TH, THead, TR } from "@/components/ui/Table";
import { ROLE_LABELS } from "@/lib/format";

/** Candidates in match-score order (the API already sorts them) with the skill gap per row. */
export function RankedTable({
  applications,
  onOpenResume,
}: {
  applications: RecruiterApplication[];
  onOpenResume: (resumeId: number) => void;
}) {
  if (applications.length === 0) return <EmptyState message="No candidates yet for this job." />;
  return (
    <Table>
      <THead>
        <tr>
          <TH className="w-10 text-right">#</TH>
          <TH>Candidate</TH>
          <TH>Match</TH>
          <TH>Skills</TH>
          <TH>Skill gap</TH>
          <TH className="hidden lg:table-cell">Exp.</TH>
          <TH className="hidden lg:table-cell">Category</TH>
          <TH>Status</TH>
          <TH className="hidden md:table-cell">Applied</TH>
          <TH>
            <span className="sr-only">Resume</span>
          </TH>
        </tr>
      </THead>
      <tbody>
        {applications.map((a, i) => (
          <TR key={a.id} className="hover:bg-surface">
            <TD className="text-right font-mono text-xs text-ink-secondary">{i + 1}</TD>
            <TD>
              <div className="font-medium">{a.candidate.name}</div>
              <div className="text-xs text-ink-secondary">{a.candidate.email}</div>
            </TD>
            <TD>
              <MatchPill score={a.match?.score} />
            </TD>
            <TD className="font-mono text-xs">{a.match?.skills_ratio ?? "--"}</TD>
            <TD>
              <div className="flex max-w-[280px] flex-wrap gap-1 py-1">
                {a.match?.skills_missing.slice(0, 4).map((s) => (
                  <Tag key={s}>{s}</Tag>
                ))}
                {(a.match?.skills_missing.length ?? 0) > 4 && (
                  <span className="text-xs text-ink-secondary">
                    +{(a.match?.skills_missing.length ?? 0) - 4}
                  </span>
                )}
                {a.match && a.match.skills_missing.length === 0 && (
                  <span className="text-xs text-status-green">None</span>
                )}
              </div>
            </TD>
            <TD className="hidden font-mono text-xs lg:table-cell">
              {a.candidate.years_experience ?? "--"}
            </TD>
            <TD className="hidden text-xs text-ink-secondary lg:table-cell">
              {a.resume?.predicted_category ? ROLE_LABELS[a.resume.predicted_category] : "--"}
            </TD>
            <TD>
              <StatusBadge status={a.status} />
            </TD>
            <TD className="hidden text-xs text-ink-secondary md:table-cell">
              <RelativeTime iso={a.applied_at} />
            </TD>
            <TD>
              {a.resume ? (
                <button
                  type="button"
                  className="text-xs text-accent hover:text-accent-hover"
                  onClick={() => onOpenResume(a.resume!.id)}
                >
                  Resume
                </button>
              ) : (
                <span className="text-xs text-ink-secondary" title="Deleted by the candidate">
                  Deleted
                </span>
              )}
            </TD>
          </TR>
        ))}
      </tbody>
    </Table>
  );
}
