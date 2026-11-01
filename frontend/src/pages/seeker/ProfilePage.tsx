import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { apiErrorMessage } from "@/api/client";
import { useDeleteAccount, useProfile, useUpdateProfile } from "@/api/queries";
import { CITIES } from "@/components/jobs/options";
import { Button } from "@/components/ui/Button";
import { Checkbox, ErrorBanner, Field, Input, Select } from "@/components/ui/Form";
import { PageHeader } from "@/components/ui/Misc";
import { Modal } from "@/components/ui/Modal";
import { TextSkeleton } from "@/components/ui/Skeleton";
import { useAuth } from "@/stores/auth";
import { toast } from "@/stores/toast";

const schema = z.object({
  full_name: z.string().trim().min(2, "Enter your full name").max(120),
  headline: z.string().trim().max(160, "Keep the headline under 160 characters"),
  current_location: z.string(),
  preferred_locations: z.array(z.string()),
  open_to_remote: z.boolean(),
  years_experience: z
    .string()
    .refine((v) => v === "" || (!Number.isNaN(Number(v)) && Number(v) >= 0 && Number(v) <= 50), {
      message: "Enter a number of years between 0 and 50",
    }),
  phone: z
    .string()
    .trim()
    .refine((v) => v === "" || /^\+?[0-9][0-9 -]{7,15}$/.test(v), {
      message: "Enter a valid phone number, e.g. +91 98765 43210",
    }),
});
type Values = z.infer<typeof schema>;

function DeleteAccount() {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const remove = useDeleteAccount();
  const clear = useAuth((s) => s.clear);
  const navigate = useNavigate();

  async function confirmDelete() {
    try {
      await remove.mutateAsync(password);
      clear();
      navigate("/login", { replace: true });
      toast("Your account and data have been deleted");
    } catch {
      /* banner */
    }
  }

  return (
    <section className="mt-6 rounded border border-status-red/30 p-4">
      <h2 className="text-base font-semibold">Delete account</h2>
      <p className="mt-1 text-sm text-ink-secondary">
        Permanently erases your account, profile, every resume file and everything read from them,
        your applications and notifications. This cannot be undone.
      </p>
      <Button className="mt-3" variant="danger" onClick={() => setOpen(true)}>
        Delete my account
      </Button>
      <Modal
        open={open}
        title="Delete your account?"
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button onClick={() => setOpen(false)}>Cancel</Button>
            <Button
              variant="danger"
              onClick={confirmDelete}
              disabled={!password || remove.isPending}
            >
              {remove.isPending ? "Deleting…" : "Delete everything"}
            </Button>
          </>
        }
      >
        <ErrorBanner message={remove.isError ? apiErrorMessage(remove.error) : null} />
        <Field label="Enter your password to confirm">
          {({ id, describedBy, invalid }) => (
            <Input
              id={id}
              type="password"
              autoComplete="current-password"
              aria-describedby={describedBy}
              invalid={invalid}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </Field>
      </Modal>
    </section>
  );
}

export default function ProfilePage() {
  const { data, isLoading } = useProfile();
  const update = useUpdateProfile();
  const { user, setUser } = useAuth();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (!data) return;
    reset({
      full_name: data.full_name,
      headline: data.headline ?? "",
      current_location: data.current_location ?? "",
      preferred_locations: data.preferred_locations,
      open_to_remote: data.open_to_remote,
      years_experience: data.years_experience === null ? "" : String(data.years_experience),
      phone: data.phone ?? "",
    });
  }, [data, reset]);

  async function onSubmit(v: Values) {
    try {
      const saved = await update.mutateAsync({
        ...v,
        headline: v.headline || null,
        current_location: v.current_location || null,
        years_experience: v.years_experience === "" ? null : Number(v.years_experience),
        phone: v.phone || null,
      });
      if (user) setUser({ ...user, full_name: saved.full_name });
      toast("Profile saved");
    } catch {
      /* banner */
    }
  }

  return (
    <div className="max-w-[720px]">
      <PageHeader title="Profile" />
      {isLoading ? (
        <TextSkeleton lines={8} />
      ) : (
        <form
          onSubmit={handleSubmit(onSubmit)}
          noValidate
          className="space-y-4 rounded border border-border p-4"
        >
          <ErrorBanner message={update.isError ? apiErrorMessage(update.error) : null} />
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Full name" error={errors.full_name?.message}>
              {({ id, describedBy, invalid }) => (
                <Input
                  id={id}
                  aria-describedby={describedBy}
                  invalid={invalid}
                  {...register("full_name")}
                />
              )}
            </Field>
            <Field label="Email" hint="Email cannot be changed.">
              {({ id, describedBy }) => (
                <Input
                  id={id}
                  aria-describedby={describedBy}
                  value={data?.email ?? ""}
                  disabled
                  readOnly
                />
              )}
            </Field>
          </div>
          <Field
            label="Headline"
            optional
            error={errors.headline?.message}
            hint="Shown to recruiters, e.g. Backend engineer, Python and PostgreSQL"
          >
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                {...register("headline")}
              />
            )}
          </Field>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Current city" optional>
              {({ id, describedBy }) => (
                <Select id={id} aria-describedby={describedBy} {...register("current_location")}>
                  <option value="">Not set</option>
                  {[
                    ...CITIES,
                    "Mumbai",
                    "Delhi",
                    "Noida",
                    "Gurugram",
                    "Kolkata",
                    "Kochi",
                    "Ahmedabad",
                    "Coimbatore",
                  ].map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Years of experience" optional error={errors.years_experience?.message}>
              {({ id, describedBy, invalid }) => (
                <Input
                  id={id}
                  inputMode="decimal"
                  aria-describedby={describedBy}
                  invalid={invalid}
                  className="font-mono"
                  {...register("years_experience")}
                />
              )}
            </Field>
          </div>
          <fieldset>
            <legend className="mb-1 text-sm font-medium">Preferred locations</legend>
            <div className="flex flex-wrap gap-x-5 gap-y-2">
              {CITIES.map((c) => (
                <Checkbox key={c} value={c} label={c} {...register("preferred_locations")} />
              ))}
            </div>
            <p className="mt-1 text-xs text-ink-secondary">
              Used for the location part of your match score.
            </p>
          </fieldset>
          <Checkbox label="Open to remote roles" {...register("open_to_remote")} />
          <Field
            label="Phone"
            optional
            error={errors.phone?.message}
            hint="Only recruiters of jobs you apply to can see this. Other job seekers never can."
          >
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                type="tel"
                autoComplete="tel"
                aria-describedby={describedBy}
                invalid={invalid}
                className="font-mono"
                {...register("phone")}
              />
            )}
          </Field>
          <div className="flex justify-end border-t border-border pt-3">
            <Button type="submit" variant="primary" disabled={!isDirty || update.isPending}>
              {update.isPending ? "Saving…" : "Save profile"}
            </Button>
          </div>
        </form>
      )}
      <DeleteAccount />
    </div>
  );
}
