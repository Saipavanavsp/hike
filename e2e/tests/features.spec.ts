import { expect, test } from "@playwright/test";
import {
  ADMIN,
  apiLogin,
  giveResume,
  jobIdByTitle,
  login,
  RECRUITER,
  registerSeeker,
  ROHAN_JOB,
} from "./helpers";

test.describe("explainable scores, interviews, alerts, analytics, companies, audit", () => {
  test("seeker sees every score component and the company page", async ({ page, request }) => {
    const seeker = await registerSeeker(request, "explain");
    await giveResume(request, seeker.auth);
    const jobId = await jobIdByTitle(request, ROHAN_JOB);
    await login(page, seeker.email, seeker.password);
    await page.goto(`/jobs/${jobId}`);
    await page.getByText("How this score is calculated").click();
    const table = page.getByRole("table", { name: "How the score is calculated" });
    for (const label of ["similarity", "Required skills", "Experience", "Location", "Match score"]) {
      await expect(table).toContainText(label);
    }
    await expect(table).toContainText("/ 100");

    // Company name links to the public company profile with its open jobs.
    const companyLink = page.locator("header").getByRole("link").first();
    const company = (await companyLink.textContent())!.trim();
    await companyLink.click();
    await expect(page).toHaveURL(/\/companies\//);
    await expect(page.getByRole("heading", { name: company })).toBeVisible();
    await expect(page.getByRole("link", { name: ROHAN_JOB })).toBeVisible();
  });

  test("recruiter schedules an interview; the seeker gets it with calendar files", async ({
    browser,
    request,
  }) => {
    const seeker = await registerSeeker(request, "interview");
    await giveResume(request, seeker.auth);
    const jobId = await jobIdByTitle(request, ROHAN_JOB);
    const app = await (
      await request.post("/api/applications", { headers: seeker.auth, data: { job_id: jobId } })
    ).json();
    const rohan = await apiLogin(request, RECRUITER.email, RECRUITER.password);
    for (const status of ["shortlisted", "interview"]) {
      const res = await request.patch(`/api/recruiter/applications/${app.id}/status`, {
        headers: rohan,
        data: { status },
      });
      expect(res.ok()).toBeTruthy();
    }

    const recCtx = await browser.newContext();
    const rp = await recCtx.newPage();
    await login(rp, RECRUITER.email, RECRUITER.password);
    await rp.goto(`/recruiter/jobs/${jobId}`);
    await expect(rp.getByText("Match scores are decision support")).toBeVisible();
    await rp.getByRole("button", { name: `Actions for ${seeker.name}` }).click();
    await rp.getByRole("menuitem", { name: "Schedule interview" }).click();
    const dialog = rp.getByRole("dialog");
    await dialog.getByLabel("Meeting link or number").fill("https://meet.example.com/e2e");
    await dialog.getByLabel("Notes for the candidate").fill("System design round");
    await dialog.getByRole("button", { name: "Schedule and send invite" }).click();
    await expect(rp.getByText(`Interview scheduled with ${seeker.name}`)).toBeVisible();
    await rp.goto("/recruiter/interviews");
    await expect(rp.getByRole("list", { name: "Interviews" })).toContainText(seeker.name);
    await recCtx.close();

    const seekerCtx = await browser.newContext();
    const sp = await seekerCtx.newPage();
    await login(sp, seeker.email, seeker.password);
    await sp.goto("/applications");
    const list = sp.getByRole("list", { name: "Interviews" });
    await expect(list).toContainText(ROHAN_JOB);
    await expect(list).toContainText("https://meet.example.com/e2e");
    const google = list.getByRole("link", { name: /Google Calendar/ });
    await expect(google).toHaveAttribute("href", /calendar\.google\.com\/calendar\/render\?action=TEMPLATE/);
    const download = sp.waitForEvent("download");
    await list.getByRole("button", { name: /Calendar file/ }).click();
    expect((await download).suggestedFilename()).toMatch(/^interview-\d+\.ics$/);
    await seekerCtx.close();

    const notes = await (await request.get("/api/notifications", { headers: seeker.auth })).json();
    expect(notes.items.map((n: { title: string }) => n.title)).toContainEqual(
      expect.stringContaining("Interview scheduled"),
    );
  });

  test("a saved search alerts the seeker when a matching job is posted", async ({
    page,
    request,
  }) => {
    const seeker = await registerSeeker(request, "alerts");
    const word = `zyxel${Date.now().toString(36)}`; // unique, so only our job matches
    await login(page, seeker.email, seeker.password);
    await page.goto(`/jobs?q=${word}`);
    await page.getByRole("button", { name: "Save search" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Save and turn on alerts" }).click();
    await expect(page.getByText("Search saved.")).toBeVisible();
    await page.goto("/saved");
    await expect(page.getByRole("list", { name: "Saved searches" })).toContainText(word);

    const rohan = await apiLogin(request, RECRUITER.email, RECRUITER.password);
    const job = await request.post("/api/recruiter/jobs", {
      headers: rohan,
      data: {
        title: `Platform Engineer (${word})`,
        role_category: "devops",
        location: "Bengaluru",
        remote_type: "hybrid",
        experience_min: 2,
        experience_max: 6,
        salary_min: 1800000,
        salary_max: 3000000,
        skills: ["Kubernetes", "Terraform"],
        description_md: `Run our ${word} platform on Kubernetes. `.repeat(4),
      },
    });
    expect(job.status(), await job.text()).toBe(201);
    await expect
      .poll(
        async () => {
          const n = await (await request.get("/api/notifications", { headers: seeker.auth })).json();
          return n.items.map((i: { type: string }) => i.type);
        },
        { timeout: 30_000 },
      )
      .toContain("saved_search_match");
    // Close it again so the seeded demo data stays tidy.
    await request.post(`/api/recruiter/jobs/${(await job.json()).id}/close`, { headers: rohan });
  });

  test("search corrects typos and understands synonyms", async ({ page, request }) => {
    const seeker = await registerSeeker(request, "typo");
    await login(page, seeker.email, seeker.password);
    await page.goto("/jobs?q=pyhton");
    await expect(page.getByRole("status").filter({ hasText: "Showing results for" })).toContainText(
      "python",
    );
    await expect(page.getByRole("list", { name: "Jobs" }).getByRole("link").first()).toBeVisible();
    await page.goto("/jobs?q=k8s");
    await expect(page.getByRole("link", { name: "DevOps Engineer", exact: true })).toBeVisible();
  });

  test("recruiter analytics and the admin audit log", async ({ browser }) => {
    const recCtx = await browser.newContext();
    const rp = await recCtx.newPage();
    await login(rp, RECRUITER.email, RECRUITER.password);
    await rp.goto("/recruiter/analytics");
    const funnel = rp.getByRole("figure", { name: "Hiring funnel" });
    await expect(funnel).toBeVisible();
    for (const stage of ["Applied", "Shortlisted", "Interview", "Offer"]) {
      await expect(funnel.getByRole("cell", { name: stage, exact: true })).toBeVisible();
    }
    await expect(rp.getByText("Median time to offer", { exact: true }).first()).toBeVisible();
    await expect(rp.getByRole("columnheader", { name: "Median time to offer" })).toBeVisible();
    await recCtx.close();

    const adminCtx = await browser.newContext();
    const ap = await adminCtx.newPage();
    await login(ap, ADMIN.email, ADMIN.password);
    await ap.goto("/admin/audit");
    await ap.getByLabel("Filter by action").selectOption("auth.");
    await expect(ap.getByRole("cell", { name: "auth.login", exact: true }).first()).toBeVisible();
    await adminCtx.close();
  });
});
