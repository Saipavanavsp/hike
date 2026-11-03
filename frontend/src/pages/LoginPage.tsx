import { zodResolver } from "@hookform/resolvers/zod";
import { FileSearch, Gauge, Workflow } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { api, apiErrorMessage, apiFieldErrors } from "@/api/client";
import { usePublicStats } from "@/api/queries";
import type { TokenResponse } from "@/api/types";
import { Logo } from "@/components/layout/Logo";
import { homeFor } from "@/components/layout/nav";
import { Button } from "@/components/ui/Button";
import { ErrorBanner, Field, Input } from "@/components/ui/Form";
import { icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs } from "@/components/ui/Tabs";
import { cn } from "@/lib/cn";
import { useAuth } from "@/stores/auth";

export const loginSchema = z.object({
  email: z.string().trim().min(1, "Enter your email").email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});
type LoginValues = z.infer<typeof loginSchema>;

export const registerSchema = z
  .object({
    role: z.enum(["seeker", "recruiter"]),
    full_name: z.string().trim().min(2, "Enter your full name"),
    email: z.string().trim().min(1, "Enter your email").email("Enter a valid email address"),
    password: z
      .string()
      .min(8, "Use at least 8 characters")
      .max(72, "Use at most 72 characters")
      .regex(/[A-Za-z]/, "Include at least one letter")
      .regex(/[0-9]/, "Include at least one number"),
    company_name: z.string().trim().max(120).optional(),
  })
  .refine((v) => v.role !== "recruiter" || !!v.company_name, {
    path: ["company_name"],
    message: "Enter the company you are hiring for",
  });
type RegisterValues = z.infer<typeof registerSchema>;

function useFinishAuth() {
  const setSession = useAuth((s) => s.setSession);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  return (data: TokenResponse) => {
    setSession(data.access_token, data.user);
    const next = params.get("next");
    navigate(next && next.startsWith("/") ? next : homeFor(data.user.role), { replace: true });
  };
}

const DEMO = [
  { label: "Job seeker", email: "rahul@example.com", password: "Seeker@123" },
  { label: "Recruiter", email: "meera@example.com", password: "Recruiter@123" },
  { label: "Admin", email: "admin@example.com", password: "Admin@123" },
];

export function LoginForm() {
  const finish = useFinishAuth();
  const [apiError, setApiError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: LoginValues) {
    setApiError(null);
    try {
      finish((await api.post<TokenResponse>("/api/auth/login", values)).data);
    } catch (err) {
      setApiError(apiErrorMessage(err));
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4" aria-label="Sign in">
      <ErrorBanner message={apiError} />
      <Field label="Email" error={errors.email?.message}>
        {({ id, describedBy, invalid }) => (
          <Input
            id={id}
            type="email"
            autoComplete="email"
            aria-describedby={describedBy}
            invalid={invalid}
            {...register("email")}
          />
        )}
      </Field>
      <Field label="Password" error={errors.password?.message}>
        {({ id, describedBy, invalid }) => (
          <Input
            id={id}
            type="password"
            autoComplete="current-password"
            aria-describedby={describedBy}
            invalid={invalid}
            {...register("password")}
          />
        )}
      </Field>
      <Button type="submit" variant="primary" className="h-10 w-full" disabled={isSubmitting}>
        {isSubmitting ? "Signing in…" : "Sign in"}
      </Button>
      <div className="rounded-lg border border-border bg-surface/60 p-3.5 text-xs text-ink-secondary">
        <p className="mb-2 text-2xs font-semibold uppercase tracking-wider text-ink-secondary">
          Demo accounts
        </p>
        <ul className="space-y-1.5">
          {DEMO.map((d) => (
            <li key={d.email} className="flex items-center justify-between gap-2">
              <span className="min-w-0">
                <span className="font-medium text-ink">{d.label}</span>:{" "}
                <span className="font-mono">{d.email}</span> /{" "}
                <span className="font-mono">{d.password}</span>
              </span>
              <button
                type="button"
                className="h-6 shrink-0 rounded-md border border-border bg-bg px-2 font-medium text-accent shadow-xs transition-colors hover:border-border-strong hover:text-accent-hover"
                onClick={() => {
                  setValue("email", d.email);
                  setValue("password", d.password);
                }}
              >
                Fill
              </button>
            </li>
          ))}
        </ul>
      </div>
    </form>
  );
}

export function RegisterForm() {
  const finish = useFinishAuth();
  const [apiError, setApiError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { role: "seeker", full_name: "", email: "", password: "", company_name: "" },
  });
  const role = watch("role");

  async function onSubmit(values: RegisterValues) {
    setApiError(null);
    try {
      const body = {
        ...values,
        company_name: values.role === "recruiter" ? values.company_name : undefined,
      };
      finish((await api.post<TokenResponse>("/api/auth/register", body)).data);
    } catch (err) {
      const fields = apiFieldErrors(err);
      Object.entries(fields).forEach(([k, msg]) =>
        setError(k as keyof RegisterValues, { message: msg }),
      );
      if (!Object.keys(fields).length) setApiError(apiErrorMessage(err));
    }
  }

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      noValidate
      className="space-y-4"
      aria-label="Create account"
    >
      <ErrorBanner message={apiError} />
      <fieldset>
        <legend className="mb-1.5 text-sm font-medium">I am a</legend>
        <div className="grid grid-cols-2 gap-2">
          {(
            [
              ["seeker", "Job seeker", "Search jobs and track applications"],
              ["recruiter", "Recruiter", "Post jobs and review candidates"],
            ] as const
          ).map(([value, title, desc]) => (
            <label
              key={value}
              className={cn(
                "cursor-pointer rounded-lg border px-3 py-2.5 text-sm transition-colors",
                role === value
                  ? "border-accent/50 bg-accent-tint ring-1 ring-accent/30"
                  : "border-border bg-bg hover:border-border-strong hover:bg-surface",
              )}
            >
              <span className="flex items-center gap-2 font-medium">
                <input
                  type="radio"
                  value={value}
                  className="accent-[rgb(var(--accent))]"
                  {...register("role")}
                />
                {title}
              </span>
              <span className="mt-0.5 block text-xs text-ink-secondary">{desc}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <Field label="Full name" error={errors.full_name?.message}>
        {({ id, describedBy, invalid }) => (
          <Input
            id={id}
            autoComplete="name"
            aria-describedby={describedBy}
            invalid={invalid}
            {...register("full_name")}
          />
        )}
      </Field>
      <Field label="Work email" error={errors.email?.message}>
        {({ id, describedBy, invalid }) => (
          <Input
            id={id}
            type="email"
            autoComplete="email"
            aria-describedby={describedBy}
            invalid={invalid}
            {...register("email")}
          />
        )}
      </Field>
      <Field
        label="Password"
        error={errors.password?.message}
        hint="At least 8 characters with a letter and a number."
      >
        {({ id, describedBy, invalid }) => (
          <Input
            id={id}
            type="password"
            autoComplete="new-password"
            aria-describedby={describedBy}
            invalid={invalid}
            {...register("password")}
          />
        )}
      </Field>
      {role === "recruiter" && (
        <Field label="Company" error={errors.company_name?.message}>
          {({ id, describedBy, invalid }) => (
            <Input
              id={id}
              autoComplete="organization"
              aria-describedby={describedBy}
              invalid={invalid}
              {...register("company_name")}
            />
          )}
        </Field>
      )}
      <Button type="submit" variant="primary" className="h-10 w-full" disabled={isSubmitting}>
        {isSubmitting ? "Creating account…" : "Create account"}
      </Button>
    </form>
  );
}

function BrowserFrame() {
  const [failed, setFailed] = useState(false);
  return (
    <figure className="w-full overflow-hidden rounded-xl border border-white/10 bg-[#0B1120] shadow-[0_30px_60px_-20px_rgb(0_0_0/0.55)]">
      <div className="flex h-9 items-center gap-2 border-b border-white/10 bg-white/[0.04] px-3.5">
        <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
        <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
        <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
        <span className="ml-3 h-5 flex-1 rounded-md bg-white/[0.06] px-2 font-mono text-[11px] leading-5 text-[#94A3B8]">
          hike / jobs
        </span>
      </div>
      {failed ? (
        <div className="flex aspect-[16/10] items-center justify-center text-sm text-[#94A3B8]">
          Dashboard screenshot
        </div>
      ) : (
        <img
          src="/screenshots/seeker-dashboard.png"
          alt="Hike job seeker dashboard with a ranked list of jobs and match scores"
          className="block w-full"
          onError={() => setFailed(true)}
        />
      )}
    </figure>
  );
}

function StatsStrip() {
  const { data, isLoading } = usePublicStats();
  if (isLoading) return <Skeleton className="h-4 w-96 max-w-full" />;
  if (!data) return null;
  const parts = [
    `${data.open_jobs} open jobs`,
    `${data.companies} companies`,
    `${data.recruiters} recruiters`,
    `${data.candidates} candidates`,
  ];
  return (
    <p className="text-sm text-ink-secondary">
      {parts.map((p, i) => (
        <span key={p}>
          {i > 0 && <span className="mx-2 text-ink-muted">·</span>}
          <span className="font-semibold text-ink tabular">{p.split(" ")[0]}</span>{" "}
          {p.split(" ").slice(1).join(" ")}
        </span>
      ))}
      {data.precision_at_5 !== null && (
        <>
          <span className="mx-2 text-ink-muted">·</span>
          match precision@5 on the labelled eval set:{" "}
          <span className="font-semibold text-ink tabular">{data.precision_at_5.toFixed(2)}</span>
        </>
      )}
    </p>
  );
}

const VALUE_PROPS = [
  {
    icon: Gauge,
    title: "Scores you can check",
    body: "Each job shows which required skills your resume covers, which are missing, and whether your experience and location fit.",
  },
  {
    icon: FileSearch,
    title: "Resume parsed, not retyped",
    body: "Upload a PDF or DOCX; skills, experience and education are extracted and you correct anything before it is saved.",
  },
  {
    icon: Workflow,
    title: "One pipeline for recruiters",
    body: "Candidates are ranked by match score and moved from Applied to Offer on a board, with every change recorded.",
  },
];

export default function LoginPage() {
  const { status, user } = useAuth();
  const [tab, setTab] = useState<"signin" | "register">("signin");
  if (status === "authenticated" && user) return <Navigate to={homeFor(user.role)} replace />;

  return (
    <div className="min-h-screen bg-canvas">
      <div className="grid min-h-[calc(100vh-56px)] lg:grid-cols-[minmax(420px,520px)_1fr]">
        <div className="flex flex-col px-6 py-6 sm:px-10">
          <Logo />
          <div className="mx-auto flex w-full max-w-[400px] flex-1 flex-col justify-center py-10">
            <div className="animate-fade-up rounded-xl border border-border bg-bg p-6 shadow-raised sm:p-8">
              <h1 className="text-2xl font-semibold">
                {tab === "signin" ? "Sign in" : "Create your account"}
              </h1>
              <p className="mb-5 mt-1.5 text-sm text-ink-secondary">
                Jobs in Bengaluru, Hyderabad, Chennai, Pune and remote.
              </p>
              <Tabs
                label="Account"
                idPrefix="auth"
                value={tab}
                onChange={setTab}
                tabs={[
                  { id: "signin", label: "Sign in" },
                  { id: "register", label: "Create account" },
                ]}
              />
              <div
                className="pt-5"
                role="tabpanel"
                id={`auth-panel-${tab}`}
                aria-labelledby={`auth-${tab}`}
              >
                {tab === "signin" ? <LoginForm /> : <RegisterForm />}
              </div>
            </div>
          </div>
        </div>
        <div className="relative hidden overflow-hidden bg-[#111827] lg:flex lg:flex-col lg:justify-center lg:px-12 lg:py-12 xl:px-16">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_50%_at_70%_0%,rgb(15_159_143/0.18),transparent_70%)]"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgb(255_255_255/0.035)_1px,transparent_1px),linear-gradient(90deg,rgb(255_255_255/0.035)_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:radial-gradient(70%_60%_at_50%_40%,black,transparent)]"
          />
          <div className="relative mx-auto w-full max-w-[760px]">
            <p className="text-sm font-medium text-[#5ED3C4]">Hiring, explained</p>
            <p className="mt-2 max-w-lg text-3xl font-semibold tracking-tight text-white">
              Match people to roles with scores you can actually read.
            </p>
            <div className="mt-8">
              <BrowserFrame />
            </div>
          </div>
        </div>
      </div>

      <section className="border-t border-border bg-bg">
        <div className="mx-auto grid max-w-[1180px] gap-6 px-6 py-10 md:grid-cols-3 md:gap-8">
          {VALUE_PROPS.map((v) => (
            <div key={v.title} className="flex gap-4">
              <span
                aria-hidden
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-accent-tint text-accent"
              >
                <v.icon {...icon} size={18} />
              </span>
              <div>
                <h2 className="text-sm font-semibold">{v.title}</h2>
                <p className="mt-1 text-sm text-ink-secondary">{v.body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
      <section className="border-t border-border bg-canvas">
        <div className="mx-auto flex max-w-[1180px] flex-wrap items-center justify-between gap-3 px-6 py-4">
          <StatsStrip />
          <p className="text-xs text-ink-secondary">
            Built by Sai Pavan ·{" "}
            <a href="https://github.com/Saipavanavsp/hike" target="_blank" rel="noreferrer">
              Source
            </a>{" "}
            ·{" "}
            <a href="/api/docs" target="_blank" rel="noreferrer">
              API docs
            </a>
          </p>
        </div>
      </section>
    </div>
  );
}
