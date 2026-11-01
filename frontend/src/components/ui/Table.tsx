import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import type { HTMLAttributes, ReactNode, TdHTMLAttributes, ThHTMLAttributes } from "react";
import { cn } from "@/lib/cn";
import { icon } from "./icon";

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("overflow-x-auto rounded border border-border", className)}>
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead className="bg-surface text-left text-xs font-medium text-ink-secondary">
      {children}
    </thead>
  );
}

export function TR({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className={cn("h-row border-b border-border last:border-b-0", className)} {...props} />
  );
}

export function TH({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope="col"
      className={cn("h-9 whitespace-nowrap px-3 font-medium", className)}
      {...props}
    />
  );
}

export function TD({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("px-3 align-middle", className)} {...props} />;
}

export type SortDir = "asc" | "desc";

interface SortableTHProps {
  label: string;
  column: string;
  sort: string;
  dir: SortDir;
  onSort: (column: string) => void;
  className?: string;
}

export function SortableTH({ label, column, sort, dir, onSort, className }: SortableTHProps) {
  const active = sort === column;
  const Icon = !active ? ChevronsUpDown : dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th
      scope="col"
      aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"}
      className={cn("h-9 whitespace-nowrap px-3 font-medium", className)}
    >
      <button
        type="button"
        onClick={() => onSort(column)}
        className={cn("inline-flex items-center gap-1 hover:text-ink", active && "text-ink")}
      >
        {label}
        <Icon {...icon} size={12} />
      </button>
    </th>
  );
}
