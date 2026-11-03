import { apiErrorMessage } from "@/api/client";
import { useRetryTask, useRunRetention, useSystemOverview } from "@/api/queries";
import type { AdminTask } from "@/api/types";
import { Tag } from "@/components/ui/Badges";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/Form";
import { EmptyState, PageHeader, RelativeTime, Section } from "@/components/ui/Misc";
import { TextSkeleton } from "@/components/ui/Skeleton";
import { Table, TD, TH, THead, TR } from "@/components/ui/Table";
import { cn } from "@/lib/cn";
import { toast } from "@/stores/toast";

function Health({ ok, label }: { ok: boolean; label?: string }) {
  return (
    <Tag
      className={cn(
        ok
          ? "border-status-green/30 bg-status-green-bg text-status-green"
          : "border-status-red/30 bg-status-red-bg text-status-red",
      )}
    >
      {label ?? (ok ? "OK" : "Down")}
    </Tag>
  );
}

const TASK_ORDER: AdminTask["status"][] = [
  "queued",
  "running",
  "retrying",
  "succeeded",
  "rejected",
  "failed",
];

export default function AdminSystemPage() {
  const { data, isLoading, error } = useSystemOverview();
  const retention = useRunRetention();
  const retry = useRetryTask();

  async function retryTask(id: string) {
    try {
      await retry.mutateAsync(id);
      toast("Task queued again");
    } catch {
      /* banner */
    }
  }

  async function runRetention() {
    try {
      await retention.mutateAsync();
      toast("Retention sweep queued");
    } catch {
      /* banner */
    }
  }

  return (
    <div className="max-w-[1000px] space-y-4">
      <PageHeader title="System" />
      <ErrorBanner message={error ? apiErrorMessage(error) : null} />
      {isLoading || !data ? (
        <TextSkeleton lines={8} />
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <Section title="Dependencies">
              <dl className="grid grid-cols-[120px_1fr] items-center gap-y-2 text-sm">
                <dt className="text-ink-secondary">PostgreSQL</dt>
                <dd className="flex items-center gap-2">
                  <Health ok={data.dependencies.postgres.ok} />
                  <span className="tabular text-xs text-ink-secondary">
                    {data.dependencies.postgres.latency_ms} ms
                  </span>
                </dd>
                <dt className="text-ink-secondary">Redis</dt>
                <dd className="flex items-center gap-2">
                  <Health ok={data.dependencies.redis.ok} />
                  <span className="tabular text-xs text-ink-secondary">
                    {data.dependencies.redis.latency_ms} ms
                  </span>
                </dd>
                <dt className="text-ink-secondary">Worker</dt>
                <dd>
                  <Health
                    ok={data.worker !== "down"}
                    label={data.worker === "inline" ? "Inline (no worker)" : undefined}
                  />
                </dd>
                <dt className="text-ink-secondary">Queue depth</dt>
                <dd className="tabular text-xs">{data.queue_depth ?? "unknown"}</dd>
                {data.dependencies.clamav && (
                  <>
                    <dt className="text-ink-secondary">ClamAV</dt>
                    <dd>
                      <Health ok={data.dependencies.clamav.ok} />
                    </dd>
                  </>
                )}
              </dl>
            </Section>
            <Section title="Background tasks, last 24 hours">
              <dl className="grid grid-cols-[120px_1fr] gap-y-2 text-sm">
                {TASK_ORDER.map((s) => (
                  <div key={s} className="contents">
                    <dt className="capitalize text-ink-secondary">{s}</dt>
                    <dd
                      className={cn(
                        "tabular text-xs leading-5",
                        s === "failed" && data.tasks_last_24h.failed > 0 && "text-status-red",
                      )}
                    >
                      {data.tasks_last_24h[s]}
                    </dd>
                  </div>
                ))}
              </dl>
            </Section>
          </div>

          <Section title={`Failed tasks (dead letter: ${data.dead_letter} waiting)`}>
            <ErrorBanner message={retry.isError ? apiErrorMessage(retry.error) : null} />
            {data.recent_failures.length === 0 ? (
              <EmptyState message="No failed tasks" />
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>Task</TH>
                    <TH>Target</TH>
                    <TH>Attempts</TH>
                    <TH>Error</TH>
                    <TH>When</TH>
                    <TH>
                      <span className="sr-only">Action</span>
                    </TH>
                  </TR>
                </THead>
                <tbody>
                  {data.recent_failures.map((t) => (
                    <TR key={t.id}>
                      <TD className="tabular text-xs">{t.kind}</TD>
                      <TD className="tabular text-xs text-ink-secondary">
                        {t.ref_type ? `${t.ref_type} ${t.ref_id}` : "--"}
                      </TD>
                      <TD className="tabular text-xs">{t.attempts}</TD>
                      <TD className="max-w-[360px] truncate text-xs" title={t.error ?? ""}>
                        {t.error}
                      </TD>
                      <TD className="text-xs text-ink-secondary">
                        <RelativeTime iso={t.created_at} />
                      </TD>
                      <TD>
                        {t.retried_as ? (
                          <span className="text-xs text-ink-secondary">Retried</span>
                        ) : (
                          <Button
                            size="sm"
                            disabled={retry.isPending}
                            onClick={() => retryTask(t.id)}
                            aria-label={`Retry ${t.kind} task`}
                          >
                            Retry
                          </Button>
                        )}
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            )}
          </Section>

          <div className="grid gap-4 md:grid-cols-2">
            <Section title="Upload security">
              <dl className="grid grid-cols-[160px_1fr] gap-y-2 text-sm">
                <dt className="text-ink-secondary">Malware scan</dt>
                <dd className="tabular text-xs leading-5">{data.security.malware_scan}</dd>
                <dt className="text-ink-secondary">Parser isolation</dt>
                <dd className="tabular text-xs leading-5">{data.security.parser_isolation}</dd>
                <dt className="text-ink-secondary">Files encrypted</dt>
                <dd>{data.security.files_encrypted ? "Yes" : "No"}</dd>
                <dt className="text-ink-secondary">Download links expire</dt>
                <dd className="tabular text-xs leading-5">
                  {data.security.signed_url_ttl_seconds}s
                </dd>
              </dl>
            </Section>
            <Section title="Data retention">
              <ErrorBanner message={retention.isError ? apiErrorMessage(retention.error) : null} />
              <dl className="grid grid-cols-[200px_1fr] gap-y-2 text-sm">
                <dt className="text-ink-secondary">Unsaved or failed uploads</dt>
                <dd className="tabular text-xs leading-5">
                  {data.retention.unconfirmed_days || "kept"}
                  {data.retention.unconfirmed_days ? " days" : ""}
                </dd>
                <dt className="text-ink-secondary">Superseded resumes</dt>
                <dd className="tabular text-xs leading-5">
                  {data.retention.old_resume_days || "kept"}
                  {data.retention.old_resume_days ? " days" : ""}
                </dd>
                <dt className="text-ink-secondary">Inactive seeker accounts</dt>
                <dd className="tabular text-xs leading-5">
                  {data.retention.inactive_seeker_days || "kept"}
                  {data.retention.inactive_seeker_days ? " days" : ""}
                </dd>
              </dl>
              <Button
                className="mt-3"
                size="sm"
                onClick={runRetention}
                disabled={retention.isPending}
              >
                Run retention sweep now
              </Button>
            </Section>
          </div>
        </>
      )}
    </div>
  );
}
