import { useState } from "react";
import { apiErrorMessage } from "@/api/client";
import { useInterviewMutations } from "@/api/queries";
import type { InterviewMode, RecruiterApplication } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorBanner, Field, Input, Select, Textarea } from "@/components/ui/Form";
import { Modal } from "@/components/ui/Modal";
import { toast } from "@/stores/toast";

function defaultStart(): string {
  // Tomorrow at 11:00 local time, in the format <input type="datetime-local"> expects.
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(11, 0, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T11:00`;
}

/** Recruiter schedules an interview; the candidate gets a notification and a calendar invite. */
export function ScheduleInterviewModal({
  app,
  onClose,
}: {
  app: RecruiterApplication | null;
  onClose: () => void;
}) {
  const { schedule } = useInterviewMutations();
  const [start, setStart] = useState(defaultStart);
  const [duration, setDuration] = useState(45);
  const [mode, setMode] = useState<InterviewMode>("video");
  const [location, setLocation] = useState("");
  const [notes, setNotes] = useState("");
  const startDate = new Date(start);
  const startError =
    Number.isNaN(startDate.getTime()) || startDate.getTime() < Date.now()
      ? "Choose a time in the future"
      : undefined;

  async function submit() {
    if (!app || startError) return;
    try {
      await schedule.mutateAsync({
        applicationId: app.id,
        body: {
          starts_at: startDate.toISOString(),
          duration_minutes: duration,
          mode,
          location,
          notes,
        },
      });
      toast(`Interview scheduled with ${app.candidate.name}`);
      onClose();
    } catch {
      /* banner */
    }
  }

  return (
    <Modal
      open={app !== null}
      title={app ? `Schedule interview: ${app.candidate.name}` : "Schedule interview"}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={submit} disabled={schedule.isPending || !!startError}>
            {schedule.isPending ? "Scheduling…" : "Schedule and send invite"}
          </Button>
        </>
      }
    >
      <ErrorBanner message={schedule.isError ? apiErrorMessage(schedule.error) : null} />
      <div className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-[1fr_120px]">
          <Field label="Date and time" error={startError}>
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                type="datetime-local"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                aria-describedby={describedBy}
                invalid={invalid}
              />
            )}
          </Field>
          <Field label="Duration">
            {({ id }) => (
              <Select
                id={id}
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
              >
                {[30, 45, 60, 90].map((m) => (
                  <option key={m} value={m}>
                    {m} min
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
        <Field label="Format">
          {({ id }) => (
            <Select id={id} value={mode} onChange={(e) => setMode(e.target.value as InterviewMode)}>
              <option value="video">Video call</option>
              <option value="phone">Phone call</option>
              <option value="onsite">On-site</option>
            </Select>
          )}
        </Field>
        <Field label={mode === "onsite" ? "Address" : "Meeting link or number"} optional>
          {({ id }) => (
            <Input
              id={id}
              value={location}
              maxLength={300}
              onChange={(e) => setLocation(e.target.value)}
            />
          )}
        </Field>
        <Field label="Notes for the candidate" optional>
          {({ id }) => (
            <Textarea
              id={id}
              rows={3}
              maxLength={1000}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          )}
        </Field>
        <p className="text-xs text-ink-secondary">
          The candidate is notified in Hike and by email, with a calendar invite (.ics) for Google
          Calendar, Outlook or Apple Calendar.
        </p>
      </div>
    </Modal>
  );
}
