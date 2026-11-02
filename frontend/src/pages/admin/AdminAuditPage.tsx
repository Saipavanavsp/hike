import { useState } from "react";
import { useAuditLog } from "@/api/queries";
import { Input, Select } from "@/components/ui/Form";
import { EmptyState, PageHeader, Pagination, RelativeTime } from "@/components/ui/Misc";
import { TableRowSkeletons } from "@/components/ui/Skeleton";
import { Table, TD, TH, THead, TR } from "@/components/ui/Table";
import { absoluteDate } from "@/lib/format";

const ACTIONS: { value: string; label: string }[] = [
  { value: "", label: "All actions" },
  { value: "admin.", label: "Admin actions" },
  { value: "auth.", label: "Sign-ins" },
  { value: "resume.", label: "Resume access and deletion" },
  { value: "application.", label: "Pipeline moves" },
  { value: "interview.", label: "Interviews" },
  { value: "job.", label: "Jobs" },
  { value: "company.", label: "Company profiles" },
  { value: "account.", label: "Account deletion" },
];

function details(d: Record<string, unknown>): string {
  return Object.entries(d)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
    .join(" · ");
}

export default function AdminAuditPage() {
  const [q, setQ] = useState("");
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const { data, isLoading } = useAuditLog({ q, action, page });

  return (
    <div>
      <PageHeader title="Audit log" />
      <div className="mb-3 flex flex-wrap gap-2">
        <Input
          aria-label="Search by actor name or email"
          placeholder="Search actor"
          className="w-64"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
        />
        <Select
          aria-label="Filter by action"
          className="w-64"
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setPage(1);
          }}
        >
          {ACTIONS.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </Select>
      </div>
      <Table>
        <THead>
          <tr>
            <TH>When</TH>
            <TH>Actor</TH>
            <TH>Action</TH>
            <TH>Target</TH>
            <TH className="hidden lg:table-cell">Details</TH>
            <TH className="hidden md:table-cell">IP / request</TH>
          </tr>
        </THead>
        <tbody>
          {isLoading && <TableRowSkeletons cols={6} />}
          {data?.items.map((e) => (
            <TR key={e.id}>
              <TD className="whitespace-nowrap text-xs" title={absoluteDate(e.created_at)}>
                <RelativeTime iso={e.created_at} />
              </TD>
              <TD className="text-xs">
                {e.actor ?? (
                  <span className="text-ink-secondary">
                    {e.actor_role ? `deleted ${e.actor_role}` : "anonymous"}
                  </span>
                )}
              </TD>
              <TD className="font-mono text-xs">{e.action}</TD>
              <TD className="font-mono text-xs text-ink-secondary">
                {e.target_type ? `${e.target_type} ${e.target_id ?? ""}` : "--"}
              </TD>
              <TD className="hidden max-w-[320px] truncate text-xs lg:table-cell">
                {details(e.details)}
              </TD>
              <TD className="hidden font-mono text-xs text-ink-secondary md:table-cell">
                {e.ip ?? "--"}
                <br />
                <span title={e.request_id ?? ""}>{e.request_id?.slice(0, 12) ?? ""}</span>
              </TD>
            </TR>
          ))}
          {data && data.items.length === 0 && (
            <tr>
              <td colSpan={6}>
                <EmptyState message="No entries match." />
              </td>
            </tr>
          )}
        </tbody>
      </Table>
      {data && (
        <Pagination
          page={data.page}
          pages={data.pages}
          total={data.total}
          pageSize={data.page_size}
          onChange={setPage}
        />
      )}
    </div>
  );
}
