import type { ReactNode } from "react";
import type { ApplicationStatus } from "@/api/types";
import { cn } from "@/lib/cn";
import { STATUS_LABELS } from "@/lib/format";

export function Tag({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-md border border-border bg-surface px-2 text-xs font-medium text-ink-secondary",
        className,
      )}
    >
      {children}
    </span>
  );
}

export type MatchTone = "green" | "amber" | "grey";

/** Thresholds from the design spec: green >= 80, amber 60-79, grey < 60. */
export function matchTone(score: number): MatchTone {
  if (score >= 80) return "green";
  if (score >= 60) return "amber";
  return "grey";
}

const toneClasses: Record<MatchTone, string> = {
  green: "bg-status-green-bg text-status-green border-status-green/25",
  amber: "bg-status-amber-bg text-status-amber border-status-amber/25",
  grey: "bg-status-grey-bg text-status-grey border-status-grey/25",
};

export function MatchPill({
  score,
  className,
}: {
  score: number | null | undefined;
  className?: string;
}) {
  if (score === null || score === undefined) {
    return <span className={cn("font-mono text-xs text-ink-secondary", className)}>--</span>;
  }
  const tone = matchTone(score);
  return (
    <span
      data-tone={tone}
      title={`${score}% match`}
      className={cn(
        "inline-flex h-6 min-w-[46px] items-center justify-center rounded-full border px-2 font-mono text-xs font-semibold tabular",
        toneClasses[tone],
        className,
      )}
    >
      {score}%
    </span>
  );
}

const statusTone: Record<ApplicationStatus, MatchTone | "red"> = {
  applied: "grey",
  shortlisted: "amber",
  interview: "amber",
  offer: "green",
  rejected: "red",
};

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  const tone = statusTone[status];
  const cls =
    tone === "red"
      ? "bg-status-red-bg text-status-red border-status-red/25"
      : toneClasses[tone as MatchTone];
  return (
    <span
      data-status={status}
      className={cn(
        "inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 text-xs font-medium",
        cls,
      )}
    >
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />
      {STATUS_LABELS[status]}
    </span>
  );
}
