import { BookmarkX } from "lucide-react";
import { useSavedJobs, useToggleSave } from "@/api/queries";
import { JobList, JobListHeader } from "@/components/jobs/JobList";
import { SavedSearchList } from "@/components/jobs/SavedSearchList";
import { IconButton } from "@/components/ui/Button";
import { icon } from "@/components/ui/icon";
import { EmptyState, PageHeader, Section } from "@/components/ui/Misc";
import { JobRowSkeletons } from "@/components/ui/Skeleton";
import { toast } from "@/stores/toast";

export default function SavedJobsPage() {
  const { data, isLoading } = useSavedJobs();
  const toggle = useToggleSave();
  return (
    <div className="space-y-4">
      <PageHeader title="Saved Jobs" />
      <div className="rounded-lg border border-border bg-bg shadow-card">
        <JobListHeader withAction />
        {isLoading && <JobRowSkeletons count={4} />}
        {data?.length === 0 && (
          <EmptyState message="No saved jobs yet." actionLabel="Browse jobs" actionTo="/jobs" />
        )}
        {data && data.length > 0 && (
          <JobList
            jobs={data}
            renderAction={(job) => (
              <IconButton
                label={`Remove ${job.title} from saved jobs`}
                onClick={() =>
                  toggle.mutate(
                    { id: job.id, saved: true },
                    { onSuccess: () => toast("Removed from saved jobs") },
                  )
                }
              >
                <BookmarkX {...icon} />
              </IconButton>
            )}
          />
        )}
      </div>
      <Section title="Saved searches and job alerts">
        <SavedSearchList />
      </Section>
    </div>
  );
}
