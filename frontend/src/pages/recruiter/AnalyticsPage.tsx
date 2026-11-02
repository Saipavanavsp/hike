import { useState } from "react";
import { Link } from "react-router-dom";
import { useRecruiterAnalytics, useRecruiterJobs } from "@/api/queries";
import { FunnelChart } from "@/components/recruiter/FunnelChart";
import { Select } from "@/components/ui/Form";
import { EmptyState, PageHeader, Section } from "@/components/ui/Misc";
import { TextSkeleton } from "@/components/ui/Skeleton";
import { Table, TD, TH, THead, TR } from "@/components/ui/Table";
import { STATUS_LABELS } from "@/lib/format";

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded border border-border p-3">
      <p className="text-xs text-ink-secondary">{label}</p>
      <p className="mt-0.5 font-mono text-xl">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-ink-secondary">{hint}</p>}
    </div>
  );
}

const days = (d: number | null) => (d === null ? "--" : `${d} d`);

export default function AnalyticsPage() {
  const { data: jobs } = useRecruiterJobs();
  const [jobId, setJobId] = useState<number | null>(null);
  const { data, isLoading } = useRecruiterAnalytics(jobId);

  return (
    <div className="max-w-[1000px] space-y-4">
      <PageHeader title="Analytics">
        <Select
          aria-label="Filter by job"
          className="w-[300px] max-w-full"
          value={jobId ?? ""}
          onChange={(e) => setJobId(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">All my jobs</option>
          {jobs?.map((j) => (
            <option key={j.id} value={j.id}>
              {j.title}
            </option>
          ))}
        </Select>
      </PageHeader>
      {isLoading || !data ? (
        <TextSkeleton lines={8} />
      ) : data.total_applications === 0 ? (
        <div className="rounded border border-border">
          <EmptyState message="No applications yet." />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Applications" value={String(data.total_applications)} />
            <Stat
              label="Offer rate"
              value={data.offer_rate === null ? "--" : `${Math.round(data.offer_rate * 100)}%`}
              hint={`${data.rejected} rejected`}
            />
            <Stat
              label="Median time to first response"
              value={days(data.median_days_to_first_response)}
            />
            <Stat
              label="Median time to offer"
              value={days(data.median_days_to_offer)}
              hint={`from ${data.offers_measured} offer${data.offers_measured === 1 ? "" : "s"}; Hike has no "hired" stage`}
            />
          </div>
          <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,320px)]">
            <Section title="Hiring funnel">
              <FunnelChart funnel={data.funnel} />
            </Section>
            <Section title="Average days in stage">
              <dl className="grid grid-cols-[1fr_auto] gap-y-2 text-sm">
                {Object.entries(data.avg_days_in_stage).map(([stage, d]) => (
                  <div key={stage} className="contents">
                    <dt className="text-ink-secondary">
                      {STATUS_LABELS[stage as keyof typeof STATUS_LABELS]}
                    </dt>
                    <dd className="font-mono text-xs leading-5">{d} d</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-2 text-xs text-ink-secondary">
                Time between entering a stage and leaving it, for candidates who have moved on.
              </p>
            </Section>
          </div>
          {jobId === null && (
            <Section title="By job">
              <Table>
                <THead>
                  <tr>
                    <TH>Job</TH>
                    <TH className="text-right">Applications</TH>
                    <TH className="text-right">Interviews</TH>
                    <TH className="text-right">Offers</TH>
                    <TH className="text-right">Median time to offer</TH>
                  </tr>
                </THead>
                <tbody>
                  {data.by_job.map((j) => (
                    <TR key={j.job_id}>
                      <TD>
                        <Link to={`/recruiter/jobs/${j.job_id}`}>{j.title}</Link>
                      </TD>
                      <TD className="text-right font-mono text-xs">{j.applications}</TD>
                      <TD className="text-right font-mono text-xs">{j.interviews}</TD>
                      <TD className="text-right font-mono text-xs">{j.offers}</TD>
                      <TD className="text-right font-mono text-xs">
                        {days(j.median_days_to_offer)}
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </Section>
          )}
        </>
      )}
    </div>
  );
}
