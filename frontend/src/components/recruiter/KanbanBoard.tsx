import {
  type Announcements,
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { MoreHorizontal } from "lucide-react";
import type { ApplicationStatus, RecruiterApplication } from "@/api/types";
import { MatchPill, Tag } from "@/components/ui/Badges";
import { Dropdown } from "@/components/ui/Dropdown";
import { icon } from "@/components/ui/icon";
import { cn } from "@/lib/cn";
import { STATUS_LABELS } from "@/lib/format";
import { canMove, COLUMNS, TRANSITIONS } from "./pipeline";

interface BoardProps {
  applications: RecruiterApplication[];
  onMove: (applicationId: number, to: ApplicationStatus) => void;
  onInvalidMove: (from: ApplicationStatus, to: ApplicationStatus) => void;
  onOpenResume: (resumeId: number) => void;
  /** Offered in the card menu for candidates in the Interview column. */
  onScheduleInterview?: (app: RecruiterApplication) => void;
}

function CandidateCard({
  app,
  onMove,
  onOpenResume,
  onScheduleInterview,
}: {
  app: RecruiterApplication;
  onMove: BoardProps["onMove"];
  onOpenResume: BoardProps["onOpenResume"];
  onScheduleInterview?: BoardProps["onScheduleInterview"];
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: app.id,
    data: { status: app.status, name: app.candidate.name },
    attributes: { roleDescription: "Draggable candidate" },
  });
  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined;
  const resume = app.resume;
  return (
    <li
      ref={setNodeRef}
      style={style}
      className={cn(
        "rounded-lg border border-border bg-bg p-3 text-sm shadow-xs transition-[box-shadow,border-color] hover:border-border-strong hover:shadow-card",
        isDragging && "relative z-20 rotate-[0.6deg] shadow-overlay",
      )}
      data-testid={`card-${app.id}`}
    >
      <div className="flex items-start gap-2">
        {/* The drag handle is the name button: focus it and press Space to pick up, arrows to move. */}
        <button
          type="button"
          className="min-w-0 flex-1 cursor-grab truncate text-left font-medium active:cursor-grabbing"
          {...listeners}
          {...attributes}
        >
          {app.candidate.name}
        </button>
        <MatchPill score={app.match?.score} />
        <Dropdown
          trigger={(p) => (
            <button
              type="button"
              aria-label={`Actions for ${app.candidate.name}`}
              className="-mr-1 inline-flex h-6 w-6 items-center justify-center rounded-md text-ink-secondary transition-colors hover:bg-surface hover:text-ink"
              {...p}
            >
              <MoreHorizontal {...icon} size={14} />
            </button>
          )}
          items={[
            ...(resume ? [{ label: "Open resume", onSelect: () => onOpenResume(resume.id) }] : []),
            ...(app.status === "interview" && onScheduleInterview
              ? [{ label: "Schedule interview", onSelect: () => onScheduleInterview(app) }]
              : []),
            ...TRANSITIONS[app.status].map((to) => ({
              label: `Move to ${STATUS_LABELS[to]}`,
              onSelect: () => onMove(app.id, to),
              danger: to === "rejected",
            })),
          ]}
        />
      </div>
      <p className="mt-1 truncate text-xs text-ink-secondary">
        {app.candidate.years_experience !== null && (
          <span className="tabular">{app.candidate.years_experience} yrs</span>
        )}
        {app.candidate.location && <> · {app.candidate.location}</>}
      </p>
      {resume ? (
        <>
          <div className="mt-2.5 flex flex-wrap gap-1">
            {resume.skills.slice(0, 4).map((s) => (
              <Tag key={s}>{s}</Tag>
            ))}
          </div>
          <button
            type="button"
            onClick={() => onOpenResume(resume.id)}
            className="mt-2.5 text-xs font-medium text-accent hover:text-accent-hover"
          >
            Resume
          </button>
        </>
      ) : (
        <p className="mt-1.5 text-xs text-ink-secondary">Resume deleted by the candidate</p>
      )}
    </li>
  );
}

const COLUMN_DOT: Record<ApplicationStatus, string> = {
  applied: "bg-status-grey",
  shortlisted: "bg-info",
  interview: "bg-status-amber",
  offer: "bg-status-green",
  rejected: "bg-status-red",
};

function Column({
  status,
  children,
  count,
}: {
  status: ApplicationStatus;
  children: React.ReactNode;
  count: number;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  return (
    <section
      ref={setNodeRef}
      aria-label={`${STATUS_LABELS[status]} column, ${count} candidates`}
      className={cn(
        "flex min-h-[220px] w-[248px] shrink-0 flex-col rounded-xl border bg-surface/70 transition-colors md:w-auto md:min-w-0 md:flex-1",
        isOver ? "border-accent bg-accent-tint/60" : "border-border",
      )}
    >
      <h3 className="flex h-11 items-center gap-2 px-3 text-sm font-semibold">
        <span aria-hidden className={cn("h-2 w-2 rounded-full", COLUMN_DOT[status])} />
        <span className="flex-1">{STATUS_LABELS[status]}</span>
        <span className="rounded-full border border-border bg-bg px-2 text-xs font-medium tabular text-ink-secondary">
          {count}
        </span>
      </h3>
      <ul className="flex flex-1 flex-col gap-2 px-2 pb-2">{children}</ul>
    </section>
  );
}

export function KanbanBoard({
  applications,
  onMove,
  onInvalidMove,
  onOpenResume,
  onScheduleInterview,
}: BoardProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor),
  );

  const byId = new Map(applications.map((a) => [a.id, a]));
  const announcements: Announcements = {
    onDragStart: ({ active }) => `Picked up ${byId.get(Number(active.id))?.candidate.name}.`,
    onDragOver: ({ over }) =>
      over
        ? `Over the ${STATUS_LABELS[over.id as ApplicationStatus]} column.`
        : "Not over a column.",
    onDragEnd: ({ active, over }) =>
      over
        ? `Moved ${byId.get(Number(active.id))?.candidate.name} to ${STATUS_LABELS[over.id as ApplicationStatus]}.`
        : "Dropped outside the board. No change.",
    onDragCancel: () => "Move cancelled.",
  };

  function handleDragEnd(e: DragEndEvent) {
    const app = byId.get(Number(e.active.id));
    const to = e.over?.id as ApplicationStatus | undefined;
    if (!app || !to || to === app.status) return;
    if (!canMove(app.status, to)) {
      onInvalidMove(app.status, to);
      return;
    }
    onMove(app.id, to);
  }

  return (
    <DndContext
      sensors={sensors}
      onDragEnd={handleDragEnd}
      accessibility={{
        announcements,
        screenReaderInstructions: {
          draggable:
            "Press Space to pick up a candidate, use the arrow keys to move between columns, and press " +
            "Space again to drop. Press Escape to cancel. Each card also has an actions menu with the same moves.",
        },
      }}
    >
      <div className="flex gap-3 overflow-x-auto pb-2" data-testid="kanban">
        {COLUMNS.map((status) => {
          const items = applications.filter((a) => a.status === status);
          return (
            <Column key={status} status={status} count={items.length}>
              {items.map((a) => (
                <CandidateCard
                  key={a.id}
                  app={a}
                  onMove={onMove}
                  onOpenResume={onOpenResume}
                  onScheduleInterview={onScheduleInterview}
                />
              ))}
              {items.length === 0 && (
                <li className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-ink-secondary">
                  No candidates
                </li>
              )}
            </Column>
          );
        })}
      </div>
    </DndContext>
  );
}
