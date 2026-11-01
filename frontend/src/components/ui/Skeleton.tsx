import { cn } from "@/lib/cn";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded-sm bg-surface", className)} />;
}

/** Placeholder rows shaped like the job table: logo, title/company, meta columns, pill. */
export function JobRowSkeletons({ count = 8 }: { count?: number }) {
  return (
    <div role="status" aria-label="Loading" className="divide-y divide-border">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="flex h-14 items-center gap-3 px-3 md:h-row">
          <Skeleton className="h-8 w-8 rounded" />
          <div className="flex flex-1 flex-col gap-1.5 md:flex-row md:items-center md:gap-3">
            <Skeleton className="h-3 w-48" />
            <Skeleton className="h-3 w-24" />
          </div>
          <Skeleton className="hidden h-3 w-20 md:block" />
          <Skeleton className="hidden h-3 w-24 md:block" />
          <Skeleton className="hidden h-3 w-12 md:block" />
          <Skeleton className="h-5 w-11" />
        </div>
      ))}
    </div>
  );
}

/** Generic table placeholder with `cols` cells per row. */
export function TableRowSkeletons({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <>
      {Array.from({ length: rows }, (_, r) => (
        <tr key={r} className="h-row border-b border-border" aria-hidden>
          {Array.from({ length: cols }, (_, c) => (
            <td key={c} className="px-3">
              <Skeleton className={cn("h-3", c === 0 ? "w-40" : "w-20")} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

export function TextSkeleton({ lines = 6 }: { lines?: number }) {
  return (
    <div role="status" aria-label="Loading" className="space-y-2">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={cn("h-3", i % 3 === 2 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}
