import { useInterviews } from "@/api/queries";
import { InterviewList } from "@/components/InterviewList";
import { PageHeader, Section } from "@/components/ui/Misc";
import { TextSkeleton } from "@/components/ui/Skeleton";

export default function InterviewsPage() {
  const { data, isLoading } = useInterviews(true);
  return (
    <div className="max-w-[900px]">
      <PageHeader title="Interviews" />
      <Section title="Upcoming">
        {isLoading || !data ? (
          <TextSkeleton lines={5} />
        ) : (
          <InterviewList interviews={data} role="recruiter" />
        )}
        <p className="mt-2 text-xs text-ink-secondary">
          Schedule an interview from a candidate&apos;s card menu in the Interview column of the
          pipeline.
        </p>
      </Section>
    </div>
  );
}
