import { useState } from "react";
import { apiErrorMessage } from "@/api/client";
import { type AdminQuery, useAdminBulk, useAdminUsers } from "@/api/queries";
import type { AdminUser } from "@/api/types";
import { AdminTable, type Column } from "@/components/admin/AdminTable";
import { Tag } from "@/components/ui/Badges";
import { PageHeader, RelativeTime } from "@/components/ui/Misc";
import { toast } from "@/stores/toast";

const columns: Column<AdminUser>[] = [
  {
    key: "id",
    label: "ID",
    className: "w-14 font-mono text-xs text-ink-secondary",
    render: (u) => u.id,
  },
  {
    key: "full_name",
    label: "Name",
    sortable: true,
    render: (u) => <span className="font-medium">{u.full_name}</span>,
  },
  {
    key: "email",
    label: "Email",
    sortable: true,
    render: (u) => <span className="text-ink-secondary">{u.email}</span>,
  },
  { key: "role", label: "Role", sortable: true, render: (u) => u.role },
  {
    key: "company",
    label: "Company",
    className: "hidden lg:table-cell text-ink-secondary",
    render: (u) => u.company ?? "",
  },
  {
    key: "is_active",
    label: "Status",
    sortable: true,
    render: (u) =>
      u.is_active ? (
        <Tag className="border-status-green/30 bg-status-green-bg text-status-green">Active</Tag>
      ) : (
        <Tag className="border-status-red/30 bg-status-red-bg text-status-red">Deactivated</Tag>
      ),
  },
  {
    key: "created_at",
    label: "Joined",
    sortable: true,
    className: "hidden md:table-cell text-xs",
    render: (u) => <RelativeTime iso={u.created_at} />,
  },
  {
    key: "last_login_at",
    label: "Last login",
    sortable: true,
    className: "hidden md:table-cell text-xs",
    render: (u) =>
      u.last_login_at ? (
        <RelativeTime iso={u.last_login_at} />
      ) : (
        <span className="text-ink-secondary">Never</span>
      ),
  },
];

function useBulk() {
  const bulk = useAdminBulk();
  return (path: string, verb: string) => async (ids: number[]) => {
    try {
      const { updated } = await bulk.mutateAsync({ path, ids });
      return `${updated} ${updated === 1 ? "user" : "users"} ${verb}`;
    } catch (err) {
      throw new Error(apiErrorMessage(err));
    }
  };
}

export default function AdminUsersPage() {
  const [query, setQuery] = useState<AdminQuery>({
    q: "",
    sort: "created_at",
    order: "desc",
    page: 1,
  });
  const { data, isLoading } = useAdminUsers(query);
  const run = useBulk();
  return (
    <div>
      <PageHeader title="Users" />
      <AdminTable
        query={query}
        setQuery={setQuery}
        data={data}
        isLoading={isLoading}
        columns={columns}
        searchPlaceholder="Search name or email"
        onDone={toast}
        bulkActions={[
          {
            label: "Deactivate",
            danger: true,
            confirm: (n) =>
              `Deactivate ${n} ${n === 1 ? "user" : "users"}? They are signed out and cannot log in until reactivated.`,
            run: run("/api/admin/users/deactivate", "deactivated"),
          },
          {
            label: "Activate",
            confirm: (n) => `Reactivate ${n} ${n === 1 ? "user" : "users"}?`,
            run: run("/api/admin/users/activate", "activated"),
          },
        ]}
      />
    </div>
  );
}
