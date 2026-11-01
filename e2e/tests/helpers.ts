import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

export const RESUME_PDF = path.resolve(
  __dirname,
  "../../backend/tests/fixtures/priya_sharma_backend.pdf",
);
export const RECRUITER = { email: "rohan@example.com", password: "Recruiter@123" };
export const OTHER_RECRUITER = { email: "meera@example.com", password: "Recruiter@123" };
export const ADMIN = { email: "admin@example.com", password: "Admin@123" };
export const ROHAN_JOB = "Backend Engineer (FastAPI)"; // seeded job owned by rohan@example.com

export async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

export type Auth = { Authorization: string };

export async function apiLogin(request: APIRequestContext, email: string, password: string) {
  const res = await request.post("/api/auth/login", { data: { email, password } });
  expect(res.status(), await res.text()).toBe(200);
  return { Authorization: `Bearer ${(await res.json()).access_token}` } as Auth;
}

/** A fresh seeker per test, so tests can run repeatedly against the same seeded database. */
export async function registerSeeker(request: APIRequestContext, label = "e2e") {
  const suffix = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  const seeker = {
    name: `E2E ${label} ${suffix}`,
    email: `${label}-${suffix}@example.com`,
    password: "E2ePass123",
  };
  const reg = await request.post("/api/auth/register", {
    data: { email: seeker.email, password: seeker.password, full_name: seeker.name, role: "seeker" },
  });
  expect(reg.status(), await reg.text()).toBe(201);
  const auth: Auth = { Authorization: `Bearer ${(await reg.json()).access_token}` };
  return { ...seeker, auth };
}

/** Upload with consent, wait for the background worker to parse it, then confirm it. */
export async function giveResume(request: APIRequestContext, auth: Auth) {
  const upload = await request.post("/api/resumes", {
    headers: auth,
    multipart: {
      file: { name: "resume.pdf", mimeType: "application/pdf", buffer: readFileSync(RESUME_PDF) },
      consent: "true",
    },
  });
  expect(upload.status(), await upload.text()).toBe(202);
  let resume = await upload.json();
  await expect
    .poll(
      async () => {
        resume = await (await request.get(`/api/resumes/${resume.id}`, { headers: auth })).json();
        return resume.status;
      },
      { timeout: 30_000 },
    )
    .toBe("ready");
  const confirm = await request.put(`/api/resumes/${resume.id}`, {
    headers: auth,
    data: { skills: resume.skills, years_experience: 2 },
  });
  expect(confirm.ok()).toBeTruthy();
  return resume.id as number;
}

export async function jobIdByTitle(request: APIRequestContext, title: string) {
  const res = await request.get("/api/jobs", { params: { q: title } });
  const job = (await res.json()).items.find((j: { title: string }) => j.title === title);
  expect(job, `seeded job "${title}"`).toBeTruthy();
  return job.id as number;
}

export function refreshCookieFrom(setCookieHeaders: string[]): string {
  const raw = setCookieHeaders.find((h) => h.startsWith("hike_refresh="));
  expect(raw, "refresh cookie").toBeTruthy();
  return raw!.split(";")[0].slice("hike_refresh=".length);
}
