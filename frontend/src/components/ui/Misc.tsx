import { ChevronLeft, ChevronRight, Inbox } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/cn";
import { absoluteDate, initials, relativeTime } from "@/lib/format";
import { icon } from "./icon";

export function EmptyState({
  message,
  actionLabel,
  actionTo,
  onAction,
}: {
  message: string;
  actionLabel?: string;
  actionTo?: string;
  onAction?: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-12 text-center text-sm text-ink-secondary">
      <span
        aria-hidden
        className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-surface text-ink-muted"
      >
        <Inbox {...icon} size={20} />
      </span>
      <p className="max-w-sm">{message}</p>
      {actionLabel && actionTo && (
        <Link
          to={actionTo}
          className="inline-flex h-8 items-center rounded-md border border-border bg-bg px-3 font-medium shadow-xs hover:border-border-strong hover:bg-surface"
        >
          {actionLabel} →
        </Link>
      )}
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="inline-flex h-8 items-center rounded-md border border-border bg-bg px-3 font-medium text-accent shadow-xs hover:border-border-strong hover:bg-surface hover:text-accent-hover"
        >
          {actionLabel} →
        </button>
      )}
    </div>
  );
}

interface PaginationProps {
  page: number;
  pages: number;
  total: number;
  pageSize: number;
  onChange: (page: number) => void;
}

function pageWindow(page: number, pages: number): (number | "…")[] {
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1);
  const out: (number | "…")[] = [1];
  const start = Math.max(2, page - 1);
  const end = Math.min(pages - 1, page + 1);
  if (start > 2) out.push("…");
  for (let p = start; p <= end; p++) out.push(p);
  if (end < pages - 1) out.push("…");
  out.push(pages);
  return out;
}

export function Pagination({ page, pages, total, pageSize, onChange }: PaginationProps) {
  if (total === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  const btn =
    "inline-flex h-8 min-w-8 items-center justify-center rounded-md border border-border bg-bg px-2 text-sm text-ink transition-colors hover:bg-surface hover:border-border-strong disabled:pointer-events-none disabled:opacity-40";
  return (
    <nav
      aria-label="Pagination"
      className="flex flex-wrap items-center justify-between gap-3 px-1 py-4 text-sm"
    >
      <span className="text-ink-secondary">
        <span className="tabular">
          {from}–{to}
        </span>{" "}
        of <span className="tabular">{total}</span>
      </span>
      <div className="flex items-center gap-1">
        <button
          className={btn}
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          aria-label="Previous page"
        >
          <ChevronLeft {...icon} />
        </button>
        {pageWindow(page, pages).map((p, i) =>
          p === "…" ? (
            <span key={`gap-${i}`} className="px-1 text-ink-secondary">
              …
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onChange(p)}
              aria-current={p === page ? "page" : undefined}
              className={cn(
                btn,
                "tabular",
                p === page &&
                  "border-primary bg-primary text-primary-fg hover:border-primary hover:bg-primary",
              )}
            >
              {p}
            </button>
          ),
        )}
        <button
          className={btn}
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
          aria-label="Next page"
        >
          <ChevronRight {...icon} />
        </button>
      </div>
    </nav>
  );
}

// Muted backgrounds for monogram logos (company content, not UI chrome).
const LOGO_COLORS = [
  "bg-[#E8EEF4] text-[#2F4A63] dark:bg-[#1C2A3B] dark:text-[#A9C1D9]",
  "bg-[#EEF0E6] text-[#4A5232] dark:bg-[#252A1C] dark:text-[#C4CBA6]",
  "bg-[#F3EBE6] text-[#6B4430] dark:bg-[#2E2219] dark:text-[#D9B9A3]",
  "bg-[#ECE8F1] text-[#4D3F63] dark:bg-[#252233] dark:text-[#C3B8D6]",
  "bg-[#E6F0EE] text-[#2E5550] dark:bg-[#17292A] dark:text-[#A3CFC8]",
  "bg-[#F1EDE3] text-[#5E5130] dark:bg-[#2B2617] dark:text-[#D3C59E]",
];

function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export function CompanyLogo({ name, size = 32 }: { name: string; size?: number }) {
  return (
    <span
      aria-hidden
      style={{ width: size, height: size }}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-lg border border-border/70 text-xs font-semibold tracking-tight",
        LOGO_COLORS[hash(name) % LOGO_COLORS.length],
      )}
    >
      {initials(name)}
    </span>
  );
}

export function RelativeTime({ iso, className }: { iso: string; className?: string }) {
  return (
    <time dateTime={iso} title={absoluteDate(iso)} className={cn("tabular", className)}>
      {relativeTime(iso)}
    </time>
  );
}

export function PageHeader({
  title,
  description,
  children,
}: {
  title: string;
  description?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold text-ink">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-ink-secondary">{description}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export function Section({
  title,
  children,
  className,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("rounded-lg border border-border bg-bg shadow-card", className)}>
      {title && <h2 className="border-b border-border px-5 py-3 text-sm font-semibold">{title}</h2>}
      <div className="p-5">{children}</div>
    </section>
  );
}
