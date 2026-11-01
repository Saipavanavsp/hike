import { FileText, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { apiErrorMessage } from "@/api/client";
import { openResumeFile } from "@/api/files";
import { useConfirmResume, useResumes, useUploadResume } from "@/api/queries";
import type { Resume } from "@/api/types";
import { SkillEditor } from "@/components/resume/SkillEditor";
import { Tag } from "@/components/ui/Badges";
import { Button } from "@/components/ui/Button";
import { ErrorBanner, Field, Input } from "@/components/ui/Form";
import { icon } from "@/components/ui/icon";
import { PageHeader, RelativeTime, Section } from "@/components/ui/Misc";
import { TextSkeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/cn";
import { formatBytes, ROLE_LABELS } from "@/lib/format";
import { toast } from "@/stores/toast";

const MAX_BYTES = 5 * 1024 * 1024;
const ACCEPT =
  ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

export function validateResumeFile(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!name.endsWith(".pdf") && !name.endsWith(".docx")) return "Choose a PDF or DOCX file.";
  if (file.size > MAX_BYTES) return `This file is ${formatBytes(file.size)}. The limit is 5 MB.`;
  if (file.size === 0) return "This file is empty.";
  return null;
}

function UploadBox({ onUploaded }: { onUploaded: (r: Resume) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const upload = useUploadResume();
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  async function handle(file: File | undefined) {
    if (!file) return;
    const problem = validateResumeFile(file);
    setError(problem);
    if (problem) return;
    try {
      onUploaded(await upload.mutateAsync(file));
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          void handle(e.dataTransfer.files[0]);
        }}
        className={cn(
          "flex flex-col items-center justify-center gap-2 rounded border border-dashed px-4 py-8 text-center",
          dragging ? "border-accent bg-accent-tint" : "border-border bg-surface",
        )}
      >
        <Upload {...icon} className="text-ink-secondary" />
        <p className="text-sm">Upload your resume (PDF or DOCX, max 5 MB)</p>
        <p className="text-xs text-ink-secondary">Drop the file here, or</p>
        <Button size="sm" onClick={() => input.current?.click()} disabled={upload.isPending}>
          {upload.isPending ? "Reading resume…" : "Choose file"}
        </Button>
        <input
          ref={input}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          aria-label="Resume file"
          onChange={(e) => {
            void handle(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </div>
      {error && (
        <p role="alert" className="mt-1 text-xs text-status-red">
          {error}
        </p>
      )}
    </div>
  );
}

function ReviewForm({ resume, onDone }: { resume: Resume; onDone: () => void }) {
  const [skills, setSkills] = useState(resume.skills);
  const [years, setYears] = useState(
    resume.years_experience === null ? "" : String(resume.years_experience),
  );
  const confirm = useConfirmResume();
  const yearsNum = years === "" ? null : Number(years);
  const yearsError =
    years !== "" && (Number.isNaN(yearsNum) || (yearsNum ?? 0) < 0 || (yearsNum ?? 0) > 50)
      ? "Enter a number of years between 0 and 50"
      : undefined;
  const p = resume.parsed;

  async function save() {
    if (yearsError) return;
    try {
      await confirm.mutateAsync({ id: resume.id, skills, years_experience: yearsNum });
      toast("Resume saved");
      onDone();
    } catch {
      /* banner */
    }
  }

  return (
    <Section title={`Review: ${resume.original_filename}`}>
      <ErrorBanner message={confirm.isError ? apiErrorMessage(confirm.error) : null} />
      <p className="mb-3 text-sm text-ink-secondary">
        We read these details from your file. Correct anything that is wrong, then save. Match
        scores use the skills and experience below.
      </p>
      <dl className="mb-4 grid grid-cols-[140px_1fr] gap-x-4 gap-y-1.5 text-sm">
        <dt className="text-ink-secondary">Name</dt>
        <dd>{p.name ?? "Not found"}</dd>
        <dt className="text-ink-secondary">Email</dt>
        <dd className="font-mono text-xs leading-5">{p.email ?? "Not found"}</dd>
        <dt className="text-ink-secondary">Phone</dt>
        <dd className="font-mono text-xs leading-5">{p.phone ?? "Not found"}</dd>
        <dt className="text-ink-secondary">Location</dt>
        <dd>{p.location ?? "Not found"}</dd>
        <dt className="text-ink-secondary">Education</dt>
        <dd>{p.education.length ? p.education.join("; ") : "Not found"}</dd>
      </dl>
      <div className="mb-4 max-w-[200px]">
        <Field
          label="Years of experience"
          error={yearsError}
          hint={p.years_experience === null ? "Could not detect; please enter it." : undefined}
        >
          {({ id, describedBy, invalid }) => (
            <Input
              id={id}
              inputMode="decimal"
              className="font-mono"
              value={years}
              onChange={(e) => setYears(e.target.value)}
              aria-describedby={describedBy}
              invalid={invalid}
            />
          )}
        </Field>
      </div>
      <p className="mb-1 text-sm font-medium">
        Skills{" "}
        <span className="font-mono text-xs font-normal text-ink-secondary">({skills.length})</span>
      </p>
      <SkillEditor value={skills} onChange={setSkills} />
      <div className="mt-4 flex justify-end gap-2 border-t border-border pt-3">
        <Button onClick={onDone}>Cancel</Button>
        <Button variant="primary" onClick={save} disabled={confirm.isPending || !!yearsError}>
          {confirm.isPending ? "Saving…" : "Save resume"}
        </Button>
      </div>
    </Section>
  );
}

export default function ResumePage() {
  const { data: resumes, isLoading } = useResumes();
  const [reviewing, setReviewing] = useState<Resume | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const current = resumes?.find((r) => r.is_current);

  async function view(id: number) {
    setFileError(null);
    try {
      await openResumeFile(id);
    } catch (err) {
      setFileError(apiErrorMessage(err));
    }
  }

  return (
    <div className="max-w-[860px] space-y-4">
      <PageHeader title="Resume" />
      {isLoading ? (
        <TextSkeleton lines={6} />
      ) : reviewing ? (
        <ReviewForm resume={reviewing} onDone={() => setReviewing(null)} />
      ) : (
        <>
          {current && (
            <Section title="Current resume">
              <ErrorBanner message={fileError} />
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-start gap-2">
                  <FileText {...icon} className="mt-0.5 text-ink-secondary" />
                  <div>
                    <p className="font-medium">{current.original_filename}</p>
                    <p className="text-xs text-ink-secondary">
                      <span className="font-mono">{formatBytes(current.size_bytes)}</span> ·
                      uploaded <RelativeTime iso={current.created_at} />
                      {current.years_experience !== null && (
                        <>
                          {" "}
                          · <span className="font-mono">{current.years_experience}</span> yrs
                          experience
                        </>
                      )}
                    </p>
                    {current.predicted_category && (
                      <p className="mt-1 text-xs text-ink-secondary">
                        Classified as {ROLE_LABELS[current.predicted_category]}
                        {current.category_confidence !== null && (
                          <span className="font-mono">
                            {" "}
                            ({Math.round(current.category_confidence * 100)}%)
                          </span>
                        )}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => view(current.id)}>
                    View file
                  </Button>
                  <Button size="sm" onClick={() => setReviewing(current)}>
                    Edit skills
                  </Button>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1">
                {current.skills.map((s) => (
                  <Tag key={s}>{s}</Tag>
                ))}
              </div>
            </Section>
          )}
          <Section title={current ? "Replace resume" : "Upload resume"}>
            <UploadBox onUploaded={setReviewing} />
          </Section>
          {resumes && resumes.length > 0 && (
            <Section title="Upload history">
              <ul className="divide-y divide-border text-sm">
                {resumes.map((r) => (
                  <li key={r.id} className="flex h-row items-center justify-between gap-3">
                    <span className="truncate">{r.original_filename}</span>
                    <span className="flex shrink-0 items-center gap-3 text-ink-secondary">
                      <RelativeTime iso={r.created_at} className="text-xs" />
                      {r.is_current ? (
                        <Tag className="border-accent/30 bg-accent-tint text-accent">Current</Tag>
                      ) : r.confirmed_at ? (
                        <button
                          className="text-xs text-accent hover:text-accent-hover"
                          onClick={() => setReviewing(r)}
                        >
                          Use this one
                        </button>
                      ) : (
                        <button
                          className="text-xs text-accent hover:text-accent-hover"
                          onClick={() => setReviewing(r)}
                        >
                          Not saved: review
                        </button>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </>
      )}
    </div>
  );
}
