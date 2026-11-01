import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";
import { z } from "zod";
import { apiErrorMessage, apiFieldErrors } from "@/api/client";
import { useJobMutations, useRecruiterJob } from "@/api/queries";
import { CITIES, ROLE_OPTIONS } from "@/components/jobs/options";
import { SkillEditor } from "@/components/resume/SkillEditor";
import { Button } from "@/components/ui/Button";
import { ErrorBanner, Field, Input, Select, Textarea } from "@/components/ui/Form";
import { PageHeader } from "@/components/ui/Misc";
import { TextSkeleton } from "@/components/ui/Skeleton";
import { useAuth } from "@/stores/auth";
import { toast } from "@/stores/toast";

const TEMPLATE = `## About the role
What the team does and what this person will own.

## Responsibilities
-

## Requirements
-

## Benefits
- `;

const num = (label: string, max: number) =>
  z
    .string()
    .trim()
    .min(1, `Enter ${label}`)
    .refine((v) => !Number.isNaN(Number(v)) && Number(v) >= 0 && Number(v) <= max, {
      message: `Enter a number between 0 and ${max}`,
    });

export const jobSchema = z
  .object({
    title: z.string().trim().min(3, "Enter a job title").max(160),
    company_name: z.string().trim().min(2, "Enter the company name").max(120),
    role_category: z.string().min(1, "Choose a role"),
    location: z.string().min(1, "Choose a location"),
    remote_type: z.enum(["onsite", "hybrid", "remote"]),
    experience_min: num("minimum years", 40),
    experience_max: num("maximum years", 40),
    salary_min: num("minimum salary", 1000),
    salary_max: num("maximum salary", 1000),
    skills: z.array(z.string()).min(1, "Add at least one skill").max(20, "Add at most 20 skills"),
    description_md: z.string().trim().min(50, "Write at least 50 characters").max(20000),
  })
  .refine((v) => Number(v.experience_min) <= Number(v.experience_max), {
    path: ["experience_max"],
    message: "Maximum must be at least the minimum",
  })
  .refine((v) => Number(v.salary_min) <= Number(v.salary_max), {
    path: ["salary_max"],
    message: "Maximum must be at least the minimum",
  })
  .refine((v) => Number(v.salary_min) > 0, {
    path: ["salary_min"],
    message: "Enter a salary above 0",
  });
type Values = z.infer<typeof jobSchema>;

const LPA = 100_000;

export default function JobFormPage() {
  const params = useParams();
  const editId = params.id ? Number(params.id) : null;
  const navigate = useNavigate();
  const user = useAuth((s) => s.user);
  const { data: existing, isLoading } = useRecruiterJob(editId);
  const { create, update } = useJobMutations();
  const [apiError, setApiError] = useState<string | null>(null);

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    setValue,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(jobSchema),
    defaultValues: {
      title: "",
      company_name: user?.company?.name ?? "",
      role_category: "",
      location: "",
      remote_type: "hybrid",
      experience_min: "",
      experience_max: "",
      salary_min: "",
      salary_max: "",
      skills: [],
      description_md: TEMPLATE,
    },
  });

  useEffect(() => {
    if (!existing) return;
    reset({
      title: existing.title,
      company_name: existing.company.name,
      role_category: existing.role_category,
      location: existing.location,
      remote_type: existing.remote_type,
      experience_min: String(existing.experience_min),
      experience_max: String(existing.experience_max),
      salary_min: String(existing.salary_min / LPA),
      salary_max: String(existing.salary_max / LPA),
      skills: existing.skills,
      description_md: existing.description_md,
    });
  }, [existing, reset]);

  const remote = watch("remote_type");
  useEffect(() => {
    if (remote === "remote") setValue("location", "Remote");
  }, [remote, setValue]);

  async function onSubmit(v: Values) {
    setApiError(null);
    const body = {
      title: v.title,
      role_category: v.role_category,
      location: v.location,
      remote_type: v.remote_type,
      experience_min: Number(v.experience_min),
      experience_max: Number(v.experience_max),
      salary_min: Math.round(Number(v.salary_min) * LPA),
      salary_max: Math.round(Number(v.salary_max) * LPA),
      skills: v.skills,
      description_md: v.description_md,
    };
    try {
      const job = editId
        ? await update.mutateAsync({ id: editId, body })
        : await create.mutateAsync({ ...body, company_name: v.company_name });
      toast(editId ? "Job updated" : "Job posted");
      navigate(`/recruiter/jobs/${job.id}`);
    } catch (err) {
      const fields = apiFieldErrors(err);
      Object.entries(fields).forEach(([k, msg]) => setError(k as keyof Values, { message: msg }));
      if (!Object.keys(fields).length) setApiError(apiErrorMessage(err));
    }
  }

  if (editId && isLoading) return <TextSkeleton lines={10} />;

  return (
    <div className="max-w-[860px]">
      <PageHeader title={editId ? "Edit job" : "Post a job"} />
      <form
        onSubmit={handleSubmit(onSubmit)}
        noValidate
        className="space-y-4 rounded border border-border p-4"
      >
        <ErrorBanner message={apiError} />
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Job title" error={errors.title?.message}>
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                {...register("title")}
              />
            )}
          </Field>
          <Field
            label="Company"
            error={errors.company_name?.message}
            hint={editId ? "Company cannot be changed after posting." : undefined}
          >
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                readOnly={!!editId}
                className={editId ? "bg-surface" : undefined}
                {...register("company_name")}
              />
            )}
          </Field>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="Role" error={errors.role_category?.message}>
            {({ id, describedBy, invalid }) => (
              <Select
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                {...register("role_category")}
              >
                <option value="">Choose…</option>
                {ROLE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Work mode" error={errors.remote_type?.message}>
            {({ id, describedBy, invalid }) => (
              <Select
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                {...register("remote_type")}
              >
                <option value="onsite">On-site</option>
                <option value="hybrid">Hybrid</option>
                <option value="remote">Remote</option>
              </Select>
            )}
          </Field>
          <Field label="Location" error={errors.location?.message}>
            {({ id, describedBy, invalid }) => (
              <Select
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                {...register("location")}
              >
                <option value="">Choose…</option>
                {[...CITIES, "Remote"].map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
        <div className="grid gap-4 md:grid-cols-4">
          <Field label="Experience min (yrs)" error={errors.experience_min?.message}>
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                inputMode="numeric"
                className="font-mono"
                aria-describedby={describedBy}
                invalid={invalid}
                {...register("experience_min")}
              />
            )}
          </Field>
          <Field label="Experience max (yrs)" error={errors.experience_max?.message}>
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                inputMode="numeric"
                className="font-mono"
                aria-describedby={describedBy}
                invalid={invalid}
                {...register("experience_max")}
              />
            )}
          </Field>
          <Field label="Salary min (LPA)" error={errors.salary_min?.message}>
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                inputMode="decimal"
                className="font-mono"
                aria-describedby={describedBy}
                invalid={invalid}
                {...register("salary_min")}
              />
            )}
          </Field>
          <Field label="Salary max (LPA)" error={errors.salary_max?.message}>
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                inputMode="decimal"
                className="font-mono"
                aria-describedby={describedBy}
                invalid={invalid}
                {...register("salary_max")}
              />
            )}
          </Field>
        </div>
        <div>
          <p className="mb-1 text-sm font-medium">Required skills</p>
          <Controller
            control={control}
            name="skills"
            render={({ field }) => <SkillEditor value={field.value} onChange={field.onChange} />}
          />
          {errors.skills && (
            <p role="alert" className="mt-1 text-xs text-status-red">
              {errors.skills.message}
            </p>
          )}
        </div>
        <Field
          label="Description"
          error={errors.description_md?.message}
          hint="Markdown. Use ## headings for About the role, Responsibilities, Requirements and Benefits."
        >
          {({ id, describedBy, invalid }) => (
            <Textarea
              id={id}
              rows={16}
              className="font-mono text-xs"
              aria-describedby={describedBy}
              invalid={invalid}
              {...register("description_md")}
            />
          )}
        </Field>
        <div className="flex justify-end gap-2 border-t border-border pt-3">
          <Button onClick={() => navigate(-1)}>Cancel</Button>
          <Button type="submit" variant="primary" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : editId ? "Save changes" : "Post job"}
          </Button>
        </div>
      </form>
    </div>
  );
}
