import { ChevronDown, ChevronRight } from "lucide-react";
import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { useInterviews, useMyApplications } from "@/api/queries";
import type { SeekerApplication } from "@/api/types";
import { InterviewList } from "@/components/InterviewList";
import { StatusBadge } from "@/components/ui/Badges";
import { icon } from "@/components/ui/icon";
import { CompanyLogo, EmptyState, PageHeader, RelativeTime, Section } from "@/components/ui/Misc";
import { TableRowSkeletons } from "@/components/ui/Skeleton";
import { Table, TD, TH, THead, TR } from "@/components/ui/Table";
import { Tabs } from "@/components/ui/Tabs";
import { absoluteDate, STATUS_LABELS } from "@/lib/format";

type Filter = "all" | "active" | "closed";

function Timeline({ app }: { app: SeekerApplication }) {
  return (
    <ol className="space-y-1.5 py-1 text-sm" aria-label="Status timeline">
      {app.history.map((h, i) => (
        <li key={i} className="flex gap-3">
          <span className="w-36 shrink-0 tabular text-xs leading-5 text-ink-secondary">
            {absoluteDate(h.changed_at)}
          </span>
          <span>
            {h.from_status === null ? (
              <>Applied</>
            ) : (
              <>
                {STATUS_LABELS[h.from_status]} →{" "}
                <span className="font-medium">{STATUS_LABELS[h.to_status]}</span>
              </>
            )}
            {h.changed_by_role === "recruiter" && h.changed_by_name && (
              <span className="text-ink-secondary"> by {h.changed_by_name}</span>
            )}
          </span>
        </li>
      ))}
      {app.note && (
        <li className="flex gap-3">
          <span className="w-36 shrink-0 text-xs leading-5 text-ink-secondary">Your note</span>
          <span className="text-ink-secondary">{app.note}</span>
        </li>
      )}
    </ol>
  );
}

export default function ApplicationsPage() {
  const { data, isLoading } = useMyApplications();
  const { data: interviews } = useInterviews(true);
  const [filter, setFilter] = useState<Filter>("all");
  const [open, setOpen] = useState<number | null>(null);

  const apps = (data ?? []).filter((a) => {
    if (filter === "active") return !["offer", "rejected"].includes(a.status);
    if (filter === "closed") return ["offer", "rejected"].includes(a.status);
    return true;
  });
  const count = (f: Filter) =>
    (data ?? []).filter((a) =>
      f === "all"
        ? true
        : f === "active"
          ? !["offer", "rejected"].includes(a.status)
          : ["offer", "rejected"].includes(a.status),
    ).length;

  return (
    <div>
      <PageHeader title="My Applications" />
      {interviews && interviews.length > 0 && (
        <div className="mb-4">
          <Section title="Upcoming interviews">
            <InterviewList interviews={interviews} role="seeker" />
          </Section>
        </div>
      )}
      <div className="mb-3">
        <Tabs
          label="Filter applications"
          idPrefix="apps"
          value={filter}
          onChange={setFilter}
          tabs={(["all", "active", "closed"] as Filter[]).map((f) => ({
            id: f,
            label: (
              <>
                {f === "all" ? "All" : f === "active" ? "In progress" : "Offer / Rejected"}{" "}
                <span className="tabular text-xs text-ink-secondary">{data ? count(f) : ""}</span>
              </>
            ),
          }))}
        />
      </div>
      {!isLoading && data?.length === 0 ? (
        <div className="rounded-lg border border-border bg-bg shadow-card">
          <EmptyState message="No applications yet." actionLabel="Browse jobs" actionTo="/jobs" />
        </div>
      ) : (
        <Table>
          <THead>
            <tr>
              <TH className="w-8">
                <span className="sr-only">Expand</span>
              </TH>
              <TH>Job</TH>
              <TH className="hidden md:table-cell">Company</TH>
              <TH>Status</TH>
              <TH className="hidden md:table-cell">Applied</TH>
              <TH className="hidden md:table-cell">Last update</TH>
            </tr>
          </THead>
          <tbody>
            {isLoading && <TableRowSkeletons cols={6} />}
            {apps.map((a) => {
              const expanded = open === a.id;
              return (
                <Fragment key={a.id}>
                  <TR className="hover:bg-surface">
                    <TD>
                      <button
                        type="button"
                        aria-expanded={expanded}
                        aria-label={`${expanded ? "Hide" : "Show"} timeline for ${a.job.title}`}
                        onClick={() => setOpen(expanded ? null : a.id)}
                        className="inline-flex h-6 w-6 items-center justify-center rounded text-ink-secondary hover:bg-bg"
                      >
                        {expanded ? <ChevronDown {...icon} /> : <ChevronRight {...icon} />}
                      </button>
                    </TD>
                    <TD>
                      <div className="flex items-center gap-2">
                        <CompanyLogo name={a.job.company.name} size={24} />
                        <Link
                          to={`/jobs/${a.job.id}`}
                          className="font-medium text-ink hover:text-accent"
                        >
                          {a.job.title}
                        </Link>
                      </div>
                    </TD>
                    <TD className="hidden text-ink-secondary md:table-cell">
                      {a.job.company.name}
                    </TD>
                    <TD>
                      <StatusBadge status={a.status} />
                    </TD>
                    <TD className="hidden text-ink-secondary md:table-cell">
                      <RelativeTime iso={a.applied_at} />
                    </TD>
                    <TD className="hidden text-ink-secondary md:table-cell">
                      <RelativeTime iso={a.updated_at} />
                    </TD>
                  </TR>
                  {expanded && (
                    <tr className="border-b border-border bg-surface">
                      <td />
                      <td colSpan={5} className="px-3 py-2">
                        <Timeline app={a} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {!isLoading && data && data.length > 0 && apps.length === 0 && (
              <tr>
                <td colSpan={6}>
                  <EmptyState message="Nothing in this view." />
                </td>
              </tr>
            )}
          </tbody>
        </Table>
      )}
    </div>
  );
}
