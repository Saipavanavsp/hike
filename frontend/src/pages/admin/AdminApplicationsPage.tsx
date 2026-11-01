import { useState } from "react";
import { type AdminQuery, useAdminApplications } from "@/api/queries";
import type { AdminApplication } from "@/api/types";
import { AdminTable, type Column } from "@/components/admin/AdminTable";
import { StatusBadge } from "@/components/ui/Badges";
import { PageHeader, RelativeTime } from "@/components/ui/Misc";

const columns: Column<AdminApplication>[] = [
  {
    key: "id",
    label: "ID",
    className: "w-14 font-mono text-xs text-ink-secondary",
    render: (a) => a.id,
  },
  {
    key: "candidate",
    label: "Candidate",
    sortable: true,
    render: (a) => (
      <>
        <span className="font-medium">{a.candidate}</span>
        <span className="ml-2 hidden text-xs text-ink-secondary xl:inline">
          {a.candidate_email}
        </span>
      </>
    ),
  },
  { key: "job_title", label: "Job", sortable: true, render: (a) => a.job_title },
  {
    key: "company",
    label: "Company",
    sortable: true,
    className: "hidden md:table-cell text-ink-secondary",
    render: (a) => a.company,
  },
  {
    key: "status",
    label: "Status",
    sortable: true,
    render: (a) => <StatusBadge status={a.status} />,
  },
  {
    key: "applied_at",
    label: "Applied",
    sortable: true,
    className: "hidden md:table-cell text-xs",
    render: (a) => <RelativeTime iso={a.applied_at} />,
  },
];

export default function AdminApplicationsPage() {
  const [query, setQuery] = useState<AdminQuery>({
    q: "",
    sort: "applied_at",
    order: "desc",
    page: 1,
  });
  const { data, isLoading } = useAdminApplications(query);
  return (
    <div>
      <PageHeader title="Applications" />
      <AdminTable
        query={query}
        setQuery={setQuery}
        data={data}
        isLoading={isLoading}
        columns={columns}
        searchPlaceholder="Search candidate, job or company"
      />
    </div>
  );
}
