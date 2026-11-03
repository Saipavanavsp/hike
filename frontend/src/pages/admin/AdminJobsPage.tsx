import { useState } from "react";
import { Link } from "react-router-dom";
import { apiErrorMessage } from "@/api/client";
import { type AdminQuery, useAdminBulk, useAdminJobs } from "@/api/queries";
import type { AdminJob } from "@/api/types";
import { AdminTable, type Column } from "@/components/admin/AdminTable";
import { Tag } from "@/components/ui/Badges";
import { PageHeader, RelativeTime } from "@/components/ui/Misc";
import { toast } from "@/stores/toast";

const columns: Column<AdminJob>[] = [
  {
    key: "id",
    label: "ID",
    className: "w-14 font-mono text-xs text-ink-secondary",
    render: (j) => j.id,
  },
  {
    key: "title",
    label: "Title",
    sortable: true,
    render: (j) => (
      <Link to={`/jobs/${j.id}`} className="font-medium text-ink hover:text-accent">
        {j.title}
      </Link>
    ),
  },
  { key: "company", label: "Company", sortable: true, render: (j) => j.company },
  {
    key: "recruiter",
    label: "Recruiter",
    sortable: true,
    className: "hidden lg:table-cell text-ink-secondary",
    render: (j) => j.recruiter,
  },
  {
    key: "location",
    label: "Location",
    sortable: true,
    className: "hidden md:table-cell",
    render: (j) => j.location,
  },
  {
    key: "applications",
    label: "Applicants",
    sortable: true,
    className: "text-right tabular",
    render: (j) => j.applications,
  },
  {
    key: "status",
    label: "Status",
    sortable: true,
    render: (j) =>
      j.status === "open" ? (
        <Tag className="border-status-green/30 bg-status-green-bg text-status-green">Open</Tag>
      ) : (
        <Tag>Closed</Tag>
      ),
  },
  {
    key: "posted_at",
    label: "Posted",
    sortable: true,
    className: "hidden md:table-cell text-xs",
    render: (j) => <RelativeTime iso={j.posted_at} />,
  },
];

export default function AdminJobsPage() {
  const [query, setQuery] = useState<AdminQuery>({
    q: "",
    sort: "posted_at",
    order: "desc",
    page: 1,
  });
  const { data, isLoading } = useAdminJobs(query);
  const bulk = useAdminBulk();
  return (
    <div>
      <PageHeader title="Jobs" />
      <AdminTable
        query={query}
        setQuery={setQuery}
        data={data}
        isLoading={isLoading}
        columns={columns}
        searchPlaceholder="Search title or company"
        onDone={toast}
        bulkActions={[
          {
            label: "Close jobs",
            danger: true,
            confirm: (n) =>
              `Close ${n} ${n === 1 ? "job" : "jobs"}? They stop accepting applications and leave search results.`,
            run: async (ids) => {
              try {
                const { updated } = await bulk.mutateAsync({ path: "/api/admin/jobs/close", ids });
                return `${updated} ${updated === 1 ? "job" : "jobs"} closed`;
              } catch (err) {
                throw new Error(apiErrorMessage(err));
              }
            },
          },
        ]}
      />
    </div>
  );
}
