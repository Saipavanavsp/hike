import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { login } from "./helpers";

/**
 * Seeker logs in, searches, opens a job, sees the match breakdown and applies.
 * The job's recruiter moves the candidate to Shortlisted. The seeker sees the new status.
 *
 * A fresh seeker is registered per run (with a resume uploaded through the API) so the
 * test can run repeatedly against the same seeded database.
 */
const JOB_TITLE = "Backend Engineer (FastAPI)"; // seeded job owned by rohan@example.com
const RECRUITER = { email: "rohan@example.com", password: "Recruiter@123" };
const RESUME = path.resolve(__dirname, "../../backend/tests/fixtures/priya_sharma_backend.pdf");

test("seeker applies, recruiter shortlists, seeker sees the new status", async ({ browser, request }) => {
  const suffix = Date.now().toString(36);
  const seeker = {
    name: `E2E Candidate ${suffix}`,
    email: `e2e-${suffix}@example.com`,
    password: "E2ePass123",
  };

  // ---- setup through the API: account + confirmed resume ----
  const reg = await request.post("/api/auth/register", {
    data: { email: seeker.email, password: seeker.password, full_name: seeker.name, role: "seeker" },
  });
  expect(reg.status()).toBe(201);
  const token = (await reg.json()).access_token as string;
  const auth = { Authorization: `Bearer ${token}` };
  const upload = await request.post("/api/resumes", {
    headers: auth,
    multipart: {
      file: { name: "resume.pdf", mimeType: "application/pdf", buffer: readFileSync(RESUME) },
    },
  });
  expect(upload.status()).toBe(201);
  const resume = await upload.json();
  const confirm = await request.put(`/api/resumes/${resume.id}`, {
    headers: auth,
    data: { skills: resume.skills, years_experience: 2 },
  });
  expect(confirm.ok()).toBeTruthy();

  // ---- seeker: log in, search, open job, check breakdown, apply ----
  const seekerCtx = await browser.newContext();
  const sp = await seekerCtx.newPage();
  await login(sp, seeker.email, seeker.password);
  await expect(sp).toHaveURL(/\/jobs/);

  const search = sp.getByRole("combobox", { name: /search jobs/i });
  await search.fill("FastAPI");
  await search.press("Enter");
  await expect(sp).toHaveURL(/q=FastAPI/);
  const row = sp.getByRole("link", { name: JOB_TITLE });
  await expect(row).toBeVisible();
  await row.click();

  await expect(sp.getByRole("heading", { name: JOB_TITLE })).toBeVisible();
  const breakdown = sp.getByLabel("Match breakdown");
  await expect(breakdown).toContainText("Skills matched:");
  await expect(breakdown).toContainText("Experience:");
  await expect(breakdown).toContainText("Location:");

  await sp.getByRole("button", { name: "Apply" }).click();
  const dialog = sp.getByRole("dialog");
  await dialog.getByLabel(/note to the recruiter/i).fill("Available to join in 30 days.");
  await dialog.getByRole("button", { name: "Send application" }).click();
  await expect(sp.getByText("Application sent")).toBeVisible();
  await expect(sp.getByText("Application status")).toBeVisible();

  // ---- recruiter: open the job pipeline and shortlist the candidate ----
  const recCtx = await browser.newContext();
  const rp = await recCtx.newPage();
  await login(rp, RECRUITER.email, RECRUITER.password);
  await expect(rp).toHaveURL(/\/recruiter/);
  const select = rp.getByLabel("Select job");
  const option = select.locator("option", { hasText: JOB_TITLE });
  await select.selectOption((await option.getAttribute("value"))!);
  await expect(rp.getByRole("heading", { name: JOB_TITLE })).toBeVisible();

  const applied = rp.getByRole("region", { name: /^Applied column/ });
  await expect(applied.getByText(seeker.name)).toBeVisible();
  await rp.getByRole("button", { name: `Actions for ${seeker.name}` }).click();
  await rp.getByRole("menuitem", { name: "Move to Shortlisted" }).click();
  await expect(rp.getByText(`${seeker.name} moved to Shortlisted`)).toBeVisible();
  const shortlisted = rp.getByRole("region", { name: /^Shortlisted column/ });
  await expect(shortlisted.getByText(seeker.name)).toBeVisible();

  // ---- seeker: sees the new status and the timeline ----
  await sp.goto("/applications");
  const appRow = sp.getByRole("row", { name: new RegExp(JOB_TITLE.replace(/[()]/g, "\\$&")) });
  await expect(appRow.getByText("Shortlisted")).toBeVisible();
  await appRow.getByRole("button", { name: /show timeline/i }).click();
  await expect(sp.getByLabel("Status timeline")).toContainText("Applied → Shortlisted");

  await seekerCtx.close();
  await recCtx.close();
});
