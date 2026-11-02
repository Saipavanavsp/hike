import { Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { useSavedSearches, useSavedSearchMutations } from "@/api/queries";
import type { SavedSearch } from "@/api/types";
import { IconButton } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Form";
import { icon } from "@/components/ui/icon";
import { EmptyState, RelativeTime } from "@/components/ui/Misc";
import { TextSkeleton } from "@/components/ui/Skeleton";
import { toast } from "@/stores/toast";

export function searchUrl(s: SavedSearch): string {
  const p = new URLSearchParams();
  if (s.params.q) p.set("q", s.params.q);
  s.params.location.forEach((v) => p.append("location", v));
  s.params.role.forEach((v) => p.append("role", v));
  s.params.remote.forEach((v) => p.append("remote", v));
  if (s.params.experience !== null) p.set("experience", String(s.params.experience));
  const q = p.toString();
  return q ? `/jobs?${q}` : "/jobs";
}

export function SavedSearchList() {
  const { data, isLoading } = useSavedSearches();
  const { toggle, remove } = useSavedSearchMutations();
  if (isLoading || !data) return <TextSkeleton lines={3} />;
  if (data.length === 0) {
    return (
      <EmptyState
        message="No saved searches. Filter the job list, then choose Save search to get alerts."
        actionLabel="Browse jobs"
        actionTo="/jobs"
      />
    );
  }
  return (
    <ul className="divide-y divide-border" aria-label="Saved searches">
      {data.map((s) => (
        <li key={s.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
          <div className="min-w-0 flex-1">
            <Link to={searchUrl(s)} className="font-medium">
              {s.name}
            </Link>
            <p className="truncate text-xs text-ink-secondary">
              {s.summary}
              {s.last_alert_at && (
                <>
                  {" "}
                  · last alert <RelativeTime iso={s.last_alert_at} />
                </>
              )}
            </p>
          </div>
          <Checkbox
            label="Alerts"
            checked={s.alerts_enabled}
            onChange={(e) =>
              toggle.mutate(
                { id: s.id, alerts_enabled: e.target.checked },
                {
                  onSuccess: (r) =>
                    toast(r.alerts_enabled ? "Alerts turned on" : "Alerts turned off"),
                },
              )
            }
          />
          <IconButton
            label={`Delete saved search ${s.name}`}
            onClick={() => remove.mutate(s.id, { onSuccess: () => toast("Saved search deleted") })}
          >
            <Trash2 {...icon} />
          </IconButton>
        </li>
      ))}
    </ul>
  );
}
