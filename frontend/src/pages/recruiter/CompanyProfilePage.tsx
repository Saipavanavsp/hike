import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiErrorMessage } from "@/api/client";
import { useMyCompany, useUpdateMyCompany } from "@/api/queries";
import { Button } from "@/components/ui/Button";
import { ErrorBanner, Field, Input, Textarea } from "@/components/ui/Form";
import { PageHeader } from "@/components/ui/Misc";
import { TextSkeleton } from "@/components/ui/Skeleton";
import { toast } from "@/stores/toast";

const FIELDS = ["website", "industry", "size_range", "hq_city", "about"] as const;
type Values = Record<(typeof FIELDS)[number], string>;

export default function CompanyProfilePage() {
  const { data, isLoading, error } = useMyCompany();
  const update = useUpdateMyCompany();
  const [values, setValues] = useState<Values | null>(null);

  useEffect(() => {
    if (data) {
      setValues(Object.fromEntries(FIELDS.map((f) => [f, data[f] ?? ""])) as Values);
    }
  }, [data]);

  const websiteError =
    values?.website && !/^https?:\/\//.test(values.website)
      ? "Start with https:// or http://"
      : undefined;

  async function save() {
    if (!values || websiteError) return;
    try {
      await update.mutateAsync(values);
      toast("Company profile saved");
    } catch {
      /* banner */
    }
  }

  if (error) return <ErrorBanner message={apiErrorMessage(error)} />;
  if (isLoading || !data || !values) return <TextSkeleton lines={8} />;
  const set = (k: keyof Values) => (e: { target: { value: string } }) =>
    setValues({ ...values, [k]: e.target.value });

  return (
    <div className="max-w-[720px]">
      <PageHeader title="Company profile">
        <Link to={`/companies/${data.slug}`} className="text-sm">
          View public page
        </Link>
      </PageHeader>
      <div className="space-y-4 rounded-lg border border-border bg-bg p-5 shadow-card">
        <ErrorBanner message={update.isError ? apiErrorMessage(update.error) : null} />
        <p className="text-sm">
          <span className="text-ink-secondary">Company: </span>
          <span className="font-medium">{data.name}</span>
        </p>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Website" optional error={websiteError}>
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                value={values.website}
                onChange={set("website")}
                placeholder="https://"
                aria-describedby={describedBy}
                invalid={invalid}
              />
            )}
          </Field>
          <Field label="Industry" optional>
            {({ id }) => <Input id={id} value={values.industry} onChange={set("industry")} />}
          </Field>
          <Field label="Company size" optional hint="For example 51-200">
            {({ id, describedBy }) => (
              <Input
                id={id}
                value={values.size_range}
                onChange={set("size_range")}
                aria-describedby={describedBy}
              />
            )}
          </Field>
          <Field label="Headquarters" optional>
            {({ id }) => <Input id={id} value={values.hq_city} onChange={set("hq_city")} />}
          </Field>
        </div>
        <Field label="About the company" optional>
          {({ id }) => (
            <Textarea
              id={id}
              rows={5}
              maxLength={1000}
              value={values.about}
              onChange={set("about")}
            />
          )}
        </Field>
        <div className="flex justify-end border-t border-border pt-3">
          <Button variant="primary" onClick={save} disabled={update.isPending || !!websiteError}>
            {update.isPending ? "Saving…" : "Save profile"}
          </Button>
        </div>
      </div>
    </div>
  );
}
