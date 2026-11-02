import { BellPlus } from "lucide-react";
import { useState } from "react";
import { apiErrorMessage } from "@/api/client";
import { type JobSearch, useSavedSearchMutations } from "@/api/queries";
import type { RemoteType, RoleCategory } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorBanner, Field, Input } from "@/components/ui/Form";
import { icon } from "@/components/ui/icon";
import { Modal } from "@/components/ui/Modal";
import { toast } from "@/stores/toast";

/** Save the current filters and get notified when a new job matches them. */
export function SaveSearchButton({ search }: { search: JobSearch }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const { create } = useSavedSearchMutations();

  function start() {
    setName(search.q ? `${search.q} jobs` : "My job search");
    create.reset();
    setOpen(true);
  }

  async function save() {
    try {
      await create.mutateAsync({
        name: name.trim(),
        params: {
          q: search.q,
          location: search.location,
          role: search.role as RoleCategory[],
          remote: search.remote as RemoteType[],
          experience: search.experience,
        },
      });
      toast("Search saved. We'll notify you when new jobs match.");
      setOpen(false);
    } catch {
      /* banner */
    }
  }

  return (
    <>
      <Button size="sm" onClick={start}>
        <BellPlus {...icon} /> Save search
      </Button>
      <Modal
        open={open}
        title="Save this search"
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={save} disabled={!name.trim() || create.isPending}>
              {create.isPending ? "Saving…" : "Save and turn on alerts"}
            </Button>
          </>
        }
      >
        <ErrorBanner message={create.isError ? apiErrorMessage(create.error) : null} />
        <Field label="Name">
          {({ id }) => (
            <Input id={id} value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
          )}
        </Field>
        <p className="mt-2 text-xs text-ink-secondary">
          When a recruiter posts a job that matches these filters, you get a notification in Hike
          and by email (unless email is turned off in your profile). Manage alerts under Saved.
        </p>
      </Modal>
    </>
  );
}
