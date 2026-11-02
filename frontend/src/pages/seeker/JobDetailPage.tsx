import { ArrowLeft, Bookmark, BookmarkCheck } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Link, useParams } from "react-router-dom";
import { apiErrorMessage } from "@/api/client";
import { useApply, useJob, useResumes, useToggleSave } from "@/api/queries";
import { MatchBreakdownPanel } from "@/components/jobs/MatchBreakdownPanel";
import { StatusBadge, Tag } from "@/components/ui/Badges";
import { Button } from "@/components/ui/Button";
import { ErrorBanner, Field, Textarea } from "@/components/ui/Form";
import { icon } from "@/components/ui/icon";
import { CompanyLogo, EmptyState, RelativeTime } from "@/components/ui/Misc";
import { Modal } from "@/components/ui/Modal";
import { Skeleton, TextSkeleton } from "@/components/ui/Skeleton";
import { formatExperience, formatSalaryRange, REMOTE_LABELS, ROLE_LABELS } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { toast } from "@/stores/toast";

function ApplyModal({
  jobId,
  title,
  open,
  onClose,
}: {
  jobId: number;
  title: string;
  open: boolean;
  onClose: () => void;
}) {
  const [note, setNote] = useState("");
  const apply = useApply();
  const tooLong = note.length > 500;
  async function submit() {
    if (tooLong) return;
    try {
      await apply.mutateAsync({ job_id: jobId, note: note.trim() || undefined });
      toast("Application sent");
      onClose();
    } catch {
      /* error shown in banner */
    }
  }
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Apply: ${title}`}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={submit} disabled={apply.isPending || tooLong}>
            {apply.isPending ? "Sending…" : "Send application"}
          </Button>
        </>
      }
    >
      <ErrorBanner message={apply.isError ? apiErrorMessage(apply.error) : null} />
      <p className="mb-3 text-ink-secondary">
        Your current resume will be shared with the recruiter.
      </p>
      <Field
        label="Note to the recruiter"
        optional
        error={tooLong ? `Keep it under 500 characters (${note.length} now)` : undefined}
        hint="For example your notice period or preferred start date."
      >
        {({ id, describedBy, invalid }) => (
          <Textarea
            id={id}
            rows={4}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            aria-describedby={describedBy}
            invalid={invalid}
          />
        )}
      </Field>
    </Modal>
  );
}

const markdownComponents = {
  h2: (p: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 className="mb-2 mt-6 text-base font-semibold first:mt-0" {...p} />
  ),
  h3: (p: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3 className="mb-1.5 mt-4 text-sm font-semibold" {...p} />
  ),
  p: (p: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className="mb-3 text-sm leading-6" {...p} />
  ),
  ul: (p: React.HTMLAttributes<HTMLUListElement>) => (
    <ul className="mb-3 list-disc space-y-1 pl-5 text-sm leading-6" {...p} />
  ),
  ol: (p: React.HTMLAttributes<HTMLOListElement>) => (
    <ol className="mb-3 list-decimal space-y-1 pl-5 text-sm leading-6" {...p} />
  ),
};

export default function JobDetailPage() {
  const id = Number(useParams().id);
  const { data: job, isLoading, isError } = useJob(id);
  const role = useAuth((s) => s.user?.role);
  const { data: resumes } = useResumes(role === "seeker");
  const toggleSave = useToggleSave();
  const [applyOpen, setApplyOpen] = useState(false);
  const isSeeker = role === "seeker";
  const hasResume = resumes?.some((r) => r.is_current) ?? false;

  if (isError)
    return (
      <EmptyState
        message="This job could not be found."
        actionLabel="Back to jobs"
        actionTo="/jobs"
      />
    );

  return (
    <div>
      <Link to="/jobs" className="mb-3 inline-flex items-center gap-1 text-sm">
        <ArrowLeft {...icon} /> Back to jobs
      </Link>
      {isLoading || !job ? (
        <div className="space-y-3">
          <Skeleton className="h-6 w-80" />
          <Skeleton className="h-4 w-56" />
          <TextSkeleton lines={10} />
        </div>
      ) : (
        <>
          <header className="mb-4 flex items-start gap-3 border-b border-border pb-4">
            <CompanyLogo name={job.company.name} size={40} />
            <div className="min-w-0 flex-1">
              <h1 className="text-xl font-semibold">{job.title}</h1>
              <p className="text-sm text-ink-secondary">
                <Link to={`/companies/${job.company.slug}`}>{job.company.name}</Link> ·{" "}
                {job.location} · {REMOTE_LABELS[job.remote_type]} · posted{" "}
                <RelativeTime iso={job.posted_at} />
              </p>
            </div>
            {job.status === "closed" && <Tag className="text-status-red">Closed</Tag>}
          </header>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
            <article aria-label="Job description" className="min-w-0">
              <ReactMarkdown components={markdownComponents}>{job.description_md}</ReactMarkdown>
              <h2 className="mb-2 mt-6 text-base font-semibold">Skills</h2>
              <div className="flex flex-wrap gap-1">
                {job.skills.map((s) => (
                  <Tag key={s}>{s}</Tag>
                ))}
              </div>
            </article>

            <aside className="lg:sticky lg:top-16 lg:self-start">
              <div className="rounded border border-border">
                <div className="space-y-2 border-b border-border p-4">
                  {isSeeker && job.application_status ? (
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-sm">
                        <span>Application status</span>
                        <StatusBadge status={job.application_status} />
                      </div>
                      <Link to="/applications" className="text-sm">
                        View timeline →
                      </Link>
                    </div>
                  ) : isSeeker ? (
                    <Button
                      variant="primary"
                      className="w-full"
                      disabled={job.status === "closed" || !hasResume}
                      onClick={() => setApplyOpen(true)}
                    >
                      {job.status === "closed" ? "No longer accepting applications" : "Apply"}
                    </Button>
                  ) : null}
                  {isSeeker && !hasResume && !job.application_status && (
                    <p className="text-xs text-ink-secondary">
                      You need a resume to apply. <Link to="/resume">Upload resume →</Link>
                    </p>
                  )}
                  {isSeeker && (
                    <Button
                      className="w-full"
                      onClick={() =>
                        toggleSave.mutate(
                          { id: job.id, saved: job.is_saved },
                          {
                            onSuccess: () =>
                              toast(job.is_saved ? "Removed from saved jobs" : "Job saved"),
                          },
                        )
                      }
                      disabled={toggleSave.isPending}
                    >
                      {job.is_saved ? <BookmarkCheck {...icon} /> : <Bookmark {...icon} />}
                      {job.is_saved ? "Saved" : "Save job"}
                    </Button>
                  )}
                </div>
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 border-b border-border p-4 text-sm">
                  <dt className="text-ink-secondary">Salary</dt>
                  <dd className="font-mono">{formatSalaryRange(job.salary_min, job.salary_max)}</dd>
                  <dt className="text-ink-secondary">Location</dt>
                  <dd>
                    {job.location} ({REMOTE_LABELS[job.remote_type]})
                  </dd>
                  <dt className="text-ink-secondary">Experience</dt>
                  <dd className="font-mono">
                    {formatExperience(job.experience_min, job.experience_max)}
                  </dd>
                  <dt className="text-ink-secondary">Role</dt>
                  <dd>{ROLE_LABELS[job.role_category]}</dd>
                </dl>
                {isSeeker && (
                  <div className="p-4">
                    {job.match ? (
                      <MatchBreakdownPanel job={job} />
                    ) : (
                      <p className="text-sm text-ink-secondary">
                        Upload a resume to see how your skills and experience match this job.{" "}
                        <Link to="/resume">Upload resume →</Link>
                      </p>
                    )}
                  </div>
                )}
              </div>
            </aside>
          </div>
          {isSeeker && (
            <ApplyModal
              jobId={job.id}
              title={job.title}
              open={applyOpen}
              onClose={() => setApplyOpen(false)}
            />
          )}
        </>
      )}
    </div>
  );
}
