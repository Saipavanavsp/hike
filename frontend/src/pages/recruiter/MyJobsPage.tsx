import { MoreHorizontal, Plus } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { apiErrorMessage } from "@/api/client";
import { useJobMutations, useRecruiterJobs } from "@/api/queries";
import { Tag } from "@/components/ui/Badges";
import { Button } from "@/components/ui/Button";
import { Dropdown } from "@/components/ui/Dropdown";
import { ErrorBanner } from "@/components/ui/Form";
import { icon } from "@/components/ui/icon";
import { EmptyState, PageHeader, RelativeTime } from "@/components/ui/Misc";
import { TableRowSkeletons } from "@/components/ui/Skeleton";
import { Table, TD, TH, THead, TR } from "@/components/ui/Table";
import { formatSalaryRange, REMOTE_LABELS } from "@/lib/format";
import { toast } from "@/stores/toast";

export default function MyJobsPage() {
  const { data, isLoading } = useRecruiterJobs();
  const { setStatus } = useJobMutations();
  const navigate = useNavigate();

  return (
    <div>
      <PageHeader title="My jobs">
        <Button variant="primary" onClick={() => navigate("/recruiter/jobs/new")}>
          <Plus {...icon} /> Post a job
        </Button>
      </PageHeader>
      <ErrorBanner message={setStatus.isError ? apiErrorMessage(setStatus.error) : null} />
      {!isLoading && data?.length === 0 ? (
        <div className="rounded border border-border">
          <EmptyState
            message="No jobs posted yet."
            actionLabel="Post a job"
            actionTo="/recruiter/jobs/new"
          />
        </div>
      ) : (
        <Table>
          <THead>
            <tr>
              <TH>Title</TH>
              <TH className="hidden md:table-cell">Company</TH>
              <TH className="hidden md:table-cell">Location</TH>
              <TH className="hidden lg:table-cell">Salary</TH>
              <TH className="text-right">Applicants</TH>
              <TH className="text-right">New</TH>
              <TH>Status</TH>
              <TH className="hidden md:table-cell">Posted</TH>
              <TH>
                <span className="sr-only">Actions</span>
              </TH>
            </tr>
          </THead>
          <tbody>
            {isLoading && <TableRowSkeletons cols={9} />}
            {data?.map((j) => (
              <TR key={j.id} className="hover:bg-surface">
                <TD>
                  <Link
                    to={`/recruiter/jobs/${j.id}`}
                    className="font-medium text-ink hover:text-accent"
                  >
                    {j.title}
                  </Link>
                </TD>
                <TD className="hidden text-ink-secondary md:table-cell">{j.company.name}</TD>
                <TD className="hidden text-ink-secondary md:table-cell">
                  {j.location} · {REMOTE_LABELS[j.remote_type]}
                </TD>
                <TD className="hidden font-mono text-xs lg:table-cell">
                  {formatSalaryRange(j.salary_min, j.salary_max)}
                </TD>
                <TD className="text-right font-mono">{j.applications_count}</TD>
                <TD className="text-right font-mono">{j.new_count}</TD>
                <TD>
                  {j.status === "open" ? (
                    <Tag className="border-status-green/30 bg-status-green-bg text-status-green">
                      Open
                    </Tag>
                  ) : (
                    <Tag>Closed</Tag>
                  )}
                </TD>
                <TD className="hidden text-xs text-ink-secondary md:table-cell">
                  <RelativeTime iso={j.posted_at} />
                </TD>
                <TD className="w-10">
                  <Dropdown
                    trigger={(p) => (
                      <button
                        type="button"
                        aria-label={`Actions for ${j.title}`}
                        className="inline-flex h-7 w-7 items-center justify-center rounded text-ink-secondary hover:bg-bg"
                        {...p}
                      >
                        <MoreHorizontal {...icon} />
                      </button>
                    )}
                    items={[
                      {
                        label: "View pipeline",
                        onSelect: () => navigate(`/recruiter/jobs/${j.id}`),
                      },
                      { label: "Edit", onSelect: () => navigate(`/recruiter/jobs/${j.id}/edit`) },
                      { label: "View public page", onSelect: () => navigate(`/jobs/${j.id}`) },
                      {
                        label: j.status === "open" ? "Close job" : "Reopen job",
                        danger: j.status === "open",
                        onSelect: () =>
                          setStatus.mutate(
                            { id: j.id, open: j.status !== "open" },
                            {
                              onSuccess: () =>
                                toast(j.status === "open" ? "Job closed" : "Job reopened"),
                            },
                          ),
                      },
                    ]}
                  />
                </TD>
              </TR>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}
