import { ExternalLink, Pencil } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { apiErrorMessage } from "@/api/client";
import { openResumeFile } from "@/api/files";
import {
  useJobApplications,
  useMoveApplication,
  useRecruiterJobs,
  useWeeklyApplications,
} from "@/api/queries";
import type { ApplicationStatus, RecruiterApplication } from "@/api/types";
import { COLUMNS } from "@/components/recruiter/pipeline";
import { KanbanBoard } from "@/components/recruiter/KanbanBoard";
import { RankedTable } from "@/components/recruiter/RankedTable";
import { ScheduleInterviewModal } from "@/components/recruiter/ScheduleInterviewModal";
import { WeeklyChart } from "@/components/recruiter/WeeklyChart";
import { Tag } from "@/components/ui/Badges";
import { ErrorBanner, Select } from "@/components/ui/Form";
import { icon } from "@/components/ui/icon";
import { EmptyState, RelativeTime } from "@/components/ui/Misc";
import { Skeleton } from "@/components/ui/Skeleton";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { formatSalaryRange, STATUS_LABELS } from "@/lib/format";
import { toast } from "@/stores/toast";

type View = "board" | "ranked";

export default function PipelinePage() {
  const params = useParams();
  const navigate = useNavigate();
  const { data: jobs, isLoading: jobsLoading } = useRecruiterJobs();
  const [view, setView] = useState<View>("board");
  const [error, setError] = useState<string | null>(null);
  const [scheduling, setScheduling] = useState<RecruiterApplication | null>(null);

  // Without a job in the URL, open the job with the most applicants.
  const busiest = jobs?.reduce<(typeof jobs)[number] | undefined>(
    (best, j) => (!best || j.applications_count > best.applications_count ? j : best),
    undefined,
  );
  const jobId = params.id ? Number(params.id) : (busiest?.id ?? null);
  const job = jobs?.find((j) => j.id === jobId);
  const { data: apps, isLoading: appsLoading } = useJobApplications(jobId);
  const { data: weekly } = useWeeklyApplications(jobId);
  const move = useMoveApplication(jobId);

  if (!jobsLoading && jobs?.length === 0) {
    return (
      <div className="rounded border border-border">
        <EmptyState
          message="You have not posted any jobs yet."
          actionLabel="Post a job"
          actionTo="/recruiter/jobs/new"
        />
      </div>
    );
  }
  if (params.id && jobs && !job) return <Navigate to="/recruiter" replace />;

  function onMove(id: number, to: ApplicationStatus) {
    setError(null);
    const name = apps?.find((a) => a.id === id)?.candidate.name ?? "Candidate";
    move.mutate(
      { id, status: to },
      {
        onSuccess: () => toast(`${name} moved to ${STATUS_LABELS[to]}`),
        onError: (err) => setError(apiErrorMessage(err)),
      },
    );
  }

  async function openResume(resumeId: number) {
    try {
      await openResumeFile(resumeId);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  const counts = Object.fromEntries(
    COLUMNS.map((s) => [s, apps?.filter((a) => a.status === s).length ?? 0]),
  );

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-ink-secondary">Job</span>
          {jobsLoading ? (
            <Skeleton className="h-8 w-72" />
          ) : (
            <Select
              aria-label="Select job"
              className="w-[320px] max-w-full"
              value={jobId ?? ""}
              onChange={(e) => navigate(`/recruiter/jobs/${e.target.value}`)}
            >
              {jobs?.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title} · {j.company.name} ({j.applications_count})
                  {j.status === "closed" ? " · closed" : ""}
                </option>
              ))}
            </Select>
          )}
        </label>
        {job && (
          <div className="ml-auto flex items-center gap-3 text-sm">
            <Link to={`/recruiter/jobs/${job.id}/edit`} className="inline-flex items-center gap-1">
              <Pencil {...icon} /> Edit job
            </Link>
            <Link to={`/jobs/${job.id}`} className="inline-flex items-center gap-1">
              <ExternalLink {...icon} /> Public page
            </Link>
          </div>
        )}
      </div>

      {job && (
        <div className="mb-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)]">
          <div className="rounded border border-border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-lg font-semibold">{job.title}</h1>
              {job.status === "closed" && <Tag className="text-status-red">Closed</Tag>}
            </div>
            <p className="text-sm text-ink-secondary">
              {job.company.name} · {job.location} ·{" "}
              <span className="font-mono">{formatSalaryRange(job.salary_min, job.salary_max)}</span>{" "}
              · posted <RelativeTime iso={job.posted_at} />
            </p>
            <dl className="mt-3 grid grid-cols-5 divide-x divide-border rounded border border-border text-center">
              {COLUMNS.map((s) => (
                <div key={s} className="py-2">
                  <dt className="text-xs text-ink-secondary">{STATUS_LABELS[s]}</dt>
                  <dd className="font-mono text-base">{counts[s]}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="rounded border border-border p-3">
            {weekly && <WeeklyChart data={weekly} />}
          </div>
        </div>
      )}

      <Tabs
        label="Candidate views"
        idPrefix="pipeline"
        value={view}
        onChange={setView}
        tabs={[
          { id: "board", label: "Pipeline" },
          { id: "ranked", label: "Ranked list" },
        ]}
      />
      <div className="pt-3">
        <p className="mb-3 rounded border border-border bg-surface px-3 py-2 text-xs text-ink-secondary">
          Match scores are decision support, not a hiring decision. They estimate resume fit from
          skills, experience, location and text similarity (with names, contacts and colleges
          removed). Review each candidate; Hike never rejects anyone automatically.
        </p>
        <ErrorBanner message={error} />
        {appsLoading || !apps ? (
          <div className="flex gap-2">
            {COLUMNS.map((c) => (
              <Skeleton key={c} className="h-48 flex-1" />
            ))}
          </div>
        ) : view === "board" ? (
          <TabPanel id="board" idPrefix="pipeline">
            <KanbanBoard
              applications={apps}
              onMove={onMove}
              onOpenResume={openResume}
              onScheduleInterview={setScheduling}
              onInvalidMove={(from, to) =>
                setError(`Cannot move from ${STATUS_LABELS[from]} to ${STATUS_LABELS[to]}.`)
              }
            />
          </TabPanel>
        ) : (
          <TabPanel id="ranked" idPrefix="pipeline">
            <RankedTable applications={apps} onOpenResume={openResume} />
          </TabPanel>
        )}
      </div>
      <ScheduleInterviewModal
        key={scheduling?.id ?? "none"}
        app={scheduling}
        onClose={() => setScheduling(null)}
      />
    </div>
  );
}
