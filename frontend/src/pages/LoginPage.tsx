import { zodResolver } from "@hookform/resolvers/zod";
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
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-3" aria-label="Sign in">
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
      <Button type="submit" variant="primary" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? "Signing in…" : "Sign in"}
      </Button>
      <div className="rounded border border-border bg-surface p-3 text-xs text-ink-secondary">
        <p className="mb-1.5 font-medium text-ink">Demo accounts</p>
        <ul className="space-y-1">
          {DEMO.map((d) => (
            <li key={d.email} className="flex items-center justify-between gap-2">
              <span>
                {d.label}: <span className="font-mono">{d.email}</span> /{" "}
                <span className="font-mono">{d.password}</span>
              </span>
              <button
                type="button"
                className="shrink-0 text-accent hover:text-accent-hover"
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
      className="space-y-3"
      aria-label="Create account"
    >
      <ErrorBanner message={apiError} />
      <fieldset>
        <legend className="mb-1 text-sm font-medium">I am a</legend>
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
                "cursor-pointer rounded border px-3 py-2 text-sm",
                role === value ? "border-accent bg-accent-tint" : "border-border hover:bg-surface",
              )}
            >
              <span className="flex items-center gap-2 font-medium">
                <input type="radio" value={value} className="accent-accent" {...register("role")} />
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
      <Button type="submit" variant="primary" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? "Creating account…" : "Create account"}
      </Button>
    </form>
  );
}

function BrowserFrame() {
  const [failed, setFailed] = useState(false);
  return (
    <figure className="w-full max-w-[760px] overflow-hidden rounded border border-border bg-bg">
      <div className="flex h-8 items-center gap-2 border-b border-border bg-surface px-3">
        <span className="h-2.5 w-2.5 rounded-sm bg-border" />
        <span className="h-2.5 w-2.5 rounded-sm bg-border" />
        <span className="h-2.5 w-2.5 rounded-sm bg-border" />
        <span className="ml-3 h-5 flex-1 rounded-sm border border-border bg-bg px-2 font-mono text-[11px] leading-5 text-ink-secondary">
          hike / jobs
        </span>
      </div>
      {failed ? (
        <div className="flex aspect-[16/10] items-center justify-center text-sm text-ink-secondary">
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
  if (isLoading) return <Skeleton className="h-4 w-96" />;
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
          {i > 0 && <span className="mx-2">·</span>}
          <span className="font-mono text-ink">{p.split(" ")[0]}</span>{" "}
          {p.split(" ").slice(1).join(" ")}
        </span>
      ))}
      {data.precision_at_5 !== null && (
        <>
          <span className="mx-2">·</span>
          match precision@5 on the labelled eval set:{" "}
          <span className="font-mono text-ink">{data.precision_at_5.toFixed(2)}</span>
        </>
      )}
    </p>
  );
}

const VALUE_PROPS = [
  {
    title: "Scores you can check",
    body: "Each job shows which required skills your resume covers, which are missing, and whether your experience and location fit.",
  },
  {
    title: "Resume parsed, not retyped",
    body: "Upload a PDF or DOCX; skills, experience and education are extracted and you correct anything before it is saved.",
  },
  {
    title: "One pipeline for recruiters",
    body: "Candidates are ranked by match score and moved from Applied to Offer on a board, with every change recorded.",
  },
];

export default function LoginPage() {
  const { status, user } = useAuth();
  const [tab, setTab] = useState<"signin" | "register">("signin");
  if (status === "authenticated" && user) return <Navigate to={homeFor(user.role)} replace />;

  return (
    <div className="min-h-screen bg-bg">
      <div className="grid min-h-[calc(100vh-64px)] lg:grid-cols-[minmax(380px,460px)_1fr]">
        <div className="flex flex-col border-border px-6 py-6 lg:border-r lg:px-10">
          <Logo />
          <div className="mt-10 w-full max-w-[360px] lg:mt-16">
            <h1 className="text-xl font-semibold">
              {tab === "signin" ? "Sign in" : "Create your account"}
            </h1>
            <p className="mb-4 mt-1 text-sm text-ink-secondary">
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
              className="pt-4"
              role="tabpanel"
              id={`auth-panel-${tab}`}
              aria-labelledby={`auth-${tab}`}
            >
              {tab === "signin" ? <LoginForm /> : <RegisterForm />}
            </div>
          </div>
        </div>
        <div className="hidden items-center justify-center bg-surface p-10 lg:flex">
          <BrowserFrame />
        </div>
      </div>

      <section className="border-t border-border">
        <div className="mx-auto grid max-w-[1180px] gap-0 px-6 md:grid-cols-3">
          {VALUE_PROPS.map((v, i) => (
            <div
              key={v.title}
              className={cn(
                "py-6 md:px-6",
                i > 0 && "border-t border-border md:border-l md:border-t-0",
              )}
            >
              <h2 className="text-sm font-semibold">{v.title}</h2>
              <p className="mt-1 text-sm text-ink-secondary">{v.body}</p>
            </div>
          ))}
        </div>
      </section>
      <section className="border-t border-border bg-surface">
        <div className="mx-auto flex max-w-[1180px] flex-wrap items-center justify-between gap-2 px-6 py-3">
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
