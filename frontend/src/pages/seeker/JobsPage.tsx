import { Link, useSearchParams } from "react-router-dom";
import { type JobSearch, useJobs, useResumes } from "@/api/queries";
import { FilterChip } from "@/components/jobs/FilterChip";
import { JobList, JobListHeader } from "@/components/jobs/JobList";
import { SaveSearchButton } from "@/components/jobs/SaveSearchButton";
import {
  EXPERIENCE_OPTIONS,
  LOCATION_OPTIONS,
  REMOTE_OPTIONS,
  ROLE_OPTIONS,
} from "@/components/jobs/options";
import { SearchBox } from "@/components/jobs/SearchBox";
import { Select } from "@/components/ui/Form";
import { EmptyState, PageHeader, Pagination } from "@/components/ui/Misc";
import { JobRowSkeletons } from "@/components/ui/Skeleton";

const SORTS: { value: JobSearch["sort"]; label: string }[] = [
  { value: "relevance", label: "Relevance" },
  { value: "newest", label: "Newest" },
  { value: "salary", label: "Salary" },
  { value: "match", label: "Match %" },
];

/** Search state lives in the URL so filters survive reloads and the back button. */
function useSearchState(): [JobSearch, (patch: Partial<JobSearch>) => void, () => void] {
  const [params, setParams] = useSearchParams();
  const exp = params.get("experience");
  const state: JobSearch = {
    q: params.get("q") ?? "",
    location: params.getAll("location"),
    role: params.getAll("role"),
    remote: params.getAll("remote"),
    experience: exp === null ? null : Number(exp),
    sort: (params.get("sort") as JobSearch["sort"]) || "relevance",
    page: Number(params.get("page") || 1),
  };
  function update(patch: Partial<JobSearch>) {
    const next = { ...state, page: 1, ...patch };
    const p = new URLSearchParams();
    if (next.q) p.set("q", next.q);
    next.location.forEach((v) => p.append("location", v));
    next.role.forEach((v) => p.append("role", v));
    next.remote.forEach((v) => p.append("remote", v));
    if (next.experience !== null) p.set("experience", String(next.experience));
    if (next.sort !== "relevance") p.set("sort", next.sort);
    if (next.page > 1) p.set("page", String(next.page));
    setParams(p);
  }
  return [state, update, () => setParams(new URLSearchParams())];
}

export default function JobsPage() {
  const [search, update, reset] = useSearchState();
  const { data, isLoading, isFetching, isError } = useJobs(search);
  const { data: resumes } = useResumes();
  const hasResume = resumes?.some((r) => r.is_current);
  const filtered =
    search.q ||
    search.location.length ||
    search.role.length ||
    search.remote.length ||
    search.experience !== null;

  return (
    <div>
      <PageHeader
        title="Find your next role"
        description="Search open positions, filter by what matters and see how well each one matches your resume."
      />
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center">
        <SearchBox value={search.q} onSearch={(q) => update({ q })} />
        <label className="flex items-center gap-2 text-sm text-ink-secondary">
          <span className="whitespace-nowrap">Sort by</span>
          <Select
            aria-label="Sort jobs"
            value={search.sort}
            onChange={(e) => update({ sort: e.target.value as JobSearch["sort"] })}
            className="w-36"
          >
            {SORTS.map((s) => (
              <option
                key={s.value}
                value={s.value}
                disabled={s.value === "match" && hasResume === false}
              >
                {s.label}
              </option>
            ))}
          </Select>
        </label>
      </div>
      <div className="mb-5 flex flex-wrap items-center gap-2" aria-label="Filters" role="group">
        <FilterChip
          label="Location"
          options={LOCATION_OPTIONS}
          selected={search.location}
          onChange={(location) => update({ location })}
        />
        <FilterChip
          label="Role"
          options={ROLE_OPTIONS}
          selected={search.role}
          onChange={(role) => update({ role })}
        />
        <FilterChip
          label="Experience"
          multiple={false}
          options={EXPERIENCE_OPTIONS}
          selected={search.experience === null ? [] : [String(search.experience)]}
          onChange={(v) => update({ experience: v.length ? Number(v[0]) : null })}
        />
        <FilterChip
          label="Remote"
          options={REMOTE_OPTIONS}
          selected={search.remote}
          onChange={(remote) => update({ remote })}
        />
        {filtered && (
          <button
            type="button"
            onClick={reset}
            className="px-1 text-sm font-medium text-accent hover:text-accent-hover"
          >
            Clear all
          </button>
        )}
        {filtered && <SaveSearchButton search={search} />}
        <span className="ml-auto text-sm text-ink-secondary" aria-live="polite">
          {data && (
            <>
              <span className="font-semibold text-ink tabular">{data.total}</span>{" "}
              {data.total === 1 ? "job" : "jobs"}
            </>
          )}
        </span>
      </div>

      {data?.corrected_query && (
        <p className="mb-4 text-sm text-ink-secondary" role="status">
          Showing results for{" "}
          <span className="font-medium text-ink">&ldquo;{data.corrected_query}&rdquo;</span> (you
          searched for &ldquo;{search.q}&rdquo;).
        </p>
      )}

      {hasResume === false && (
        <p className="mb-4 rounded-lg border border-border bg-surface/70 px-4 py-2.5 text-sm text-ink-secondary">
          Match scores appear once you upload a resume. <Link to="/resume">Upload resume →</Link>
        </p>
      )}

      <div
        className={`rounded-lg border border-border bg-bg shadow-card transition-opacity ${isFetching && !isLoading ? "opacity-70" : ""}`}
      >
        <JobListHeader />
        {isLoading && <JobRowSkeletons />}
        {isError && <EmptyState message="Could not load jobs." />}
        {data && data.items.length === 0 && (
          <EmptyState
            message="No jobs match these filters."
            actionLabel="Clear filters"
            onAction={reset}
          />
        )}
        {data && data.items.length > 0 && <JobList jobs={data.items} />}
      </div>
      {data && (
        <Pagination
          page={data.page}
          pages={data.pages}
          total={data.total}
          pageSize={data.page_size}
          onChange={(page) => {
            update({ page });
            window.scrollTo({ top: 0 });
          }}
        />
      )}
    </div>
  );
}
