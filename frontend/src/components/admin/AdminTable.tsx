import { Search } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import type { AdminQuery } from "@/api/queries";
import type { Page } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Checkbox, ErrorBanner } from "@/components/ui/Form";
import { icon } from "@/components/ui/icon";
import { EmptyState, Pagination } from "@/components/ui/Misc";
import { Modal } from "@/components/ui/Modal";
import { TableRowSkeletons } from "@/components/ui/Skeleton";
import { SortableTH, Table, TD, TH, THead, TR } from "@/components/ui/Table";

export interface Column<T> {
  key: string;
  label: string;
  sortable?: boolean;
  className?: string;
  render: (row: T) => ReactNode;
}

export interface BulkAction {
  label: string;
  /** Confirmation text, e.g. "Deactivate 3 users? They will be signed out." */
  confirm: (n: number) => string;
  run: (ids: number[]) => Promise<string>; // resolves with the toast message
  danger?: boolean;
}

interface AdminTableProps<T extends { id: number }> {
  query: AdminQuery;
  setQuery: (q: AdminQuery) => void;
  data: Page<T> | undefined;
  isLoading: boolean;
  columns: Column<T>[];
  bulkActions?: BulkAction[];
  searchPlaceholder: string;
  onDone?: (message: string) => void;
}

export function AdminTable<T extends { id: number }>({
  query,
  setQuery,
  data,
  isLoading,
  columns,
  bulkActions = [],
  searchPlaceholder,
  onDone,
}: AdminTableProps<T>) {
  const [text, setText] = useState(query.q);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [pending, setPending] = useState<BulkAction | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      if (text !== query.q) setQuery({ ...query, q: text, page: 1 });
    }, 250);
    return () => clearTimeout(t);
  }, [text, query, setQuery]);

  useEffect(() => setSelected(new Set()), [query]);

  const rows = data?.items ?? [];
  const allChecked = rows.length > 0 && rows.every((r) => selected.has(r.id));
  const withBulk = bulkActions.length > 0;

  function sortBy(column: string) {
    const order = query.sort === column && query.order === "asc" ? "desc" : "asc";
    setQuery({ ...query, sort: column, order, page: 1 });
  }

  async function confirm() {
    if (!pending) return;
    setRunning(true);
    setError(null);
    try {
      const message = await pending.run([...selected]);
      setSelected(new Set());
      setPending(null);
      onDone?.(message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-[320px]">
          <Search
            {...icon}
            className="pointer-events-none absolute left-2.5 top-2 text-ink-secondary"
          />
          <input
            type="search"
            aria-label={searchPlaceholder}
            placeholder={searchPlaceholder}
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="h-9 w-full rounded-md border border-border bg-bg pl-9 pr-3 text-sm text-ink shadow-xs placeholder:text-ink-muted transition-[border-color,box-shadow] hover:border-border-strong focus:border-accent focus:outline-none focus:ring-[3px] focus:ring-accent/20"
          />
        </div>
        {withBulk && (
          <div className="ml-auto flex items-center gap-2 text-sm">
            <span className="text-ink-secondary">
              <span className="tabular text-ink">{selected.size}</span> selected
            </span>
            {bulkActions.map((a) => (
              <Button
                key={a.label}
                size="sm"
                variant={a.danger ? "danger" : "secondary"}
                disabled={selected.size === 0}
                onClick={() => setPending(a)}
              >
                {a.label}
              </Button>
            ))}
          </div>
        )}
      </div>
      <Table>
        <THead>
          <tr>
            {withBulk && (
              <TH className="w-9">
                <Checkbox
                  aria-label="Select all rows on this page"
                  checked={allChecked}
                  onChange={() =>
                    setSelected(allChecked ? new Set() : new Set(rows.map((r) => r.id)))
                  }
                />
              </TH>
            )}
            {columns.map((c) =>
              c.sortable ? (
                <SortableTH
                  key={c.key}
                  label={c.label}
                  column={c.key}
                  sort={query.sort}
                  dir={query.order}
                  onSort={sortBy}
                  className={c.className}
                />
              ) : (
                <TH key={c.key} className={c.className}>
                  {c.label}
                </TH>
              ),
            )}
          </tr>
        </THead>
        <tbody>
          {isLoading && <TableRowSkeletons cols={columns.length + (withBulk ? 1 : 0)} />}
          {rows.map((row) => (
            <TR
              key={row.id}
              className={selected.has(row.id) ? "bg-accent-tint" : "hover:bg-surface"}
            >
              {withBulk && (
                <TD>
                  <Checkbox
                    aria-label={`Select row ${row.id}`}
                    checked={selected.has(row.id)}
                    onChange={() => {
                      const next = new Set(selected);
                      if (next.has(row.id)) next.delete(row.id);
                      else next.add(row.id);
                      setSelected(next);
                    }}
                  />
                </TD>
              )}
              {columns.map((c) => (
                <TD key={c.key} className={c.className}>
                  {c.render(row)}
                </TD>
              ))}
            </TR>
          ))}
          {!isLoading && rows.length === 0 && (
            <tr>
              <td colSpan={columns.length + 1}>
                <EmptyState message="No rows match this search." />
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
          onChange={(page) => setQuery({ ...query, page })}
        />
      )}
      <Modal
        open={!!pending}
        title={pending?.label ?? ""}
        onClose={() => setPending(null)}
        footer={
          <>
            <Button onClick={() => setPending(null)}>Cancel</Button>
            <Button
              variant={pending?.danger ? "danger" : "primary"}
              onClick={confirm}
              disabled={running}
            >
              {running ? "Working…" : pending?.label}
            </Button>
          </>
        }
      >
        <ErrorBanner message={error} />
        <p>{pending?.confirm(selected.size)}</p>
      </Modal>
    </div>
  );
}
