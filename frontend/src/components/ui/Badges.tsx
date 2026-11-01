import type { ReactNode } from "react";
import type { ApplicationStatus } from "@/api/types";
import { cn } from "@/lib/cn";
import { STATUS_LABELS } from "@/lib/format";

export function Tag({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center rounded-sm border border-border bg-surface px-1.5 text-xs text-ink-secondary",
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
  green: "bg-status-green-bg text-status-green border-status-green/30",
  amber: "bg-status-amber-bg text-status-amber border-status-amber/30",
  grey: "bg-status-grey-bg text-status-grey border-status-grey/30",
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
        "inline-flex h-5 min-w-[42px] items-center justify-center rounded-sm border px-1.5 font-mono text-xs font-medium tabular",
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
      ? "bg-status-red-bg text-status-red border-status-red/30"
      : toneClasses[tone as MatchTone];
  return (
    <span
      data-status={status}
      className={cn(
        "inline-flex h-5 items-center rounded-sm border px-1.5 text-xs font-medium",
        cls,
      )}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}
