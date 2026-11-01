import { ChevronLeft, ChevronRight } from "lucide-react";
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
    <div className="px-4 py-10 text-center text-sm text-ink-secondary">
      {message}{" "}
      {actionLabel && actionTo && (
        <Link to={actionTo} className="font-medium">
          {actionLabel} →
        </Link>
      )}
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="font-medium text-accent hover:text-accent-hover"
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
    "inline-flex h-7 min-w-7 items-center justify-center rounded border border-border px-2 text-sm disabled:opacity-40";
  return (
    <nav
      aria-label="Pagination"
      className="flex items-center justify-between gap-3 px-1 py-3 text-sm"
    >
      <span className="text-ink-secondary">
        <span className="font-mono tabular">
          {from}–{to}
        </span>{" "}
        of <span className="font-mono tabular">{total}</span>
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
                "font-mono",
                p === page && "border-accent bg-accent-tint text-accent",
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
  "bg-[#E8EEF4] text-[#2F4A63]",
  "bg-[#EEF0E6] text-[#4A5232]",
  "bg-[#F3EBE6] text-[#6B4430]",
  "bg-[#ECE8F1] text-[#4D3F63]",
  "bg-[#E6F0EE] text-[#2E5550]",
  "bg-[#F1EDE3] text-[#5E5130]",
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
        "inline-flex shrink-0 items-center justify-center rounded border border-border font-mono text-xs font-medium",
        LOGO_COLORS[hash(name) % LOGO_COLORS.length],
      )}
    >
      {initials(name)}
    </span>
  );
}

export function RelativeTime({ iso, className }: { iso: string; className?: string }) {
  return (
    <time dateTime={iso} title={absoluteDate(iso)} className={cn("font-mono tabular", className)}>
      {relativeTime(iso)}
    </time>
  );
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h1 className="text-xl font-semibold">{title}</h1>
      {children && <div className="flex items-center gap-2">{children}</div>}
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
    <section className={cn("rounded border border-border bg-bg", className)}>
      {title && (
        <h2 className="border-b border-border px-4 py-2.5 text-sm font-semibold">{title}</h2>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}
