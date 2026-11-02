import { ExternalLink } from "lucide-react";
import { useParams } from "react-router-dom";
import { apiErrorMessage } from "@/api/client";
import { useCompanyPage } from "@/api/queries";
import { JobList } from "@/components/jobs/JobList";
import { ErrorBanner } from "@/components/ui/Form";
import { icon } from "@/components/ui/icon";
import { CompanyLogo, EmptyState, Section } from "@/components/ui/Misc";
import { TextSkeleton } from "@/components/ui/Skeleton";

export default function CompanyPage() {
  const { slug = "" } = useParams();
  const { data, isLoading, error } = useCompanyPage(slug);
  if (error) return <ErrorBanner message={apiErrorMessage(error)} />;
  if (isLoading || !data) return <TextSkeleton lines={8} />;
  const c = data.company;
  const facts = [c.industry, c.size_range && `${c.size_range} employees`, c.hq_city].filter(
    Boolean,
  );
  return (
    <div className="max-w-[900px] space-y-4">
      <div className="flex items-start gap-3">
        <CompanyLogo name={c.name} size={48} />
        <div>
          <h1 className="text-2xl font-semibold">{c.name}</h1>
          <p className="text-sm text-ink-secondary">{facts.join(" · ")}</p>
          {c.website && (
            <a
              href={c.website}
              target="_blank"
              rel="noreferrer noopener"
              className="mt-1 inline-flex items-center gap-1 text-sm"
            >
              {c.website.replace(/^https?:\/\//, "")} <ExternalLink {...icon} />
            </a>
          )}
        </div>
      </div>
      {c.about && (
        <Section title="About">
          <p className="whitespace-pre-line text-sm">{c.about}</p>
        </Section>
      )}
      <Section title={`Open jobs (${data.open_jobs.length})`}>
        {data.open_jobs.length === 0 ? (
          <EmptyState message="No open jobs right now." />
        ) : (
          <JobList jobs={data.open_jobs} />
        )}
      </Section>
    </div>
  );
}
