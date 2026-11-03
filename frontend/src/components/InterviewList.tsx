import { CalendarPlus, Download } from "lucide-react";
import { useState } from "react";
import { apiErrorMessage } from "@/api/client";
import { downloadInterviewIcs } from "@/api/files";
import { useInterviewMutations } from "@/api/queries";
import type { Interview } from "@/api/types";
import { Tag } from "@/components/ui/Badges";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/Form";
import { icon } from "@/components/ui/icon";
import { EmptyState } from "@/components/ui/Misc";
import { toast } from "@/stores/toast";

const MODE = { video: "Video call", phone: "Phone call", onsite: "On-site" } as const;

export function formatInterviewTime(iso: string, minutes: number): string {
  const start = new Date(iso);
  const end = new Date(start.getTime() + minutes * 60_000);
  const day = start.toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
  const t = (d: Date) => d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
  return `${day}, ${t(start)} – ${t(end)}`;
}

/** Upcoming interviews with calendar actions. Recruiters can also cancel. */
export function InterviewList({
  interviews,
  role,
}: {
  interviews: Interview[];
  role: "seeker" | "recruiter";
}) {
  const { cancel } = useInterviewMutations();
  const [error, setError] = useState<string | null>(null);

  async function ics(id: number) {
    setError(null);
    try {
      await downloadInterviewIcs(id);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function cancelOne(iv: Interview) {
    try {
      await cancel.mutateAsync(iv.id);
      toast(`Interview with ${iv.candidate_name} cancelled; the candidate was notified`);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  if (interviews.length === 0) return <EmptyState message="No upcoming interviews." />;
  return (
    <div>
      <ErrorBanner message={error} />
      <ul className="divide-y divide-border" aria-label="Interviews">
        {interviews.map((iv) => (
          <li key={iv.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
            <div className="min-w-0">
              <p className="font-medium">
                {role === "recruiter" ? iv.candidate_name : iv.job_title}
                <span className="font-normal text-ink-secondary">
                  {" "}
                  · {role === "recruiter" ? iv.job_title : iv.company}
                </span>
                {iv.status === "cancelled" && <Tag className="ml-2 text-status-red">Cancelled</Tag>}
              </p>
              <p className="tabular text-xs leading-5">
                {formatInterviewTime(iv.starts_at, iv.duration_minutes)}
              </p>
              <p className="text-xs text-ink-secondary">
                {MODE[iv.mode]}
                {iv.location &&
                  (iv.location.startsWith("http") ? (
                    <>
                      {" "}
                      ·{" "}
                      <a href={iv.location} target="_blank" rel="noreferrer noopener">
                        {iv.location}
                      </a>
                    </>
                  ) : (
                    <> · {iv.location}</>
                  ))}
              </p>
              {iv.notes && <p className="mt-1 text-xs text-ink-secondary">{iv.notes}</p>}
            </div>
            {iv.status === "scheduled" && (
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={() => ics(iv.id)}>
                  <Download {...icon} /> Calendar file
                </Button>
                <a
                  className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-bg px-3 text-sm font-medium text-ink no-underline shadow-xs transition-colors hover:border-border-strong hover:bg-surface hover:text-ink"
                  href={iv.google_calendar_url}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  <CalendarPlus {...icon} /> Google Calendar
                </a>
                {role === "recruiter" && (
                  <Button
                    size="sm"
                    variant="danger"
                    disabled={cancel.isPending}
                    onClick={() => cancelOne(iv)}
                  >
                    Cancel
                  </Button>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
