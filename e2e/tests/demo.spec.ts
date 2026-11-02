import { expect, test, type Page } from "@playwright/test";
import { copyFileSync, mkdirSync } from "node:fs";
import path from "node:path";

/** Silent demo video: seeker, recruiter and admin workflows with on-screen captions. */

async function caption(page: Page, text: string, ms = 2200) {
  await page.evaluate((t) => {
    let el = document.getElementById("demo-caption");
    if (!el) {
      el = document.createElement("div");
      el.id = "demo-caption";
      el.setAttribute(
        "style",
        "position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:99999;" +
          "background:rgba(26,29,33,.92);color:#fff;padding:10px 18px;border-radius:6px;" +
          "font:500 16px 'IBM Plex Sans',system-ui,sans-serif;max-width:80%;text-align:center;" +
          "pointer-events:none",
      );
      document.body.appendChild(el);
    }
    el.textContent = t;
  }, text);
  await page.waitForTimeout(ms);
}

async function signIn(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

async function signOut(page: Page, name: string) {
  await page.getByRole("button", { name }).click();
  await page.getByRole("menuitem", { name: /sign out/i }).click();
  await expect(page).toHaveURL(/\/login/);
}

test("demo", async ({ page }, testInfo) => {
  await page.goto("/login");
  await caption(page, "Hike: a job portal with explainable, privacy-aware matching", 3000);

  // ---- seeker ----
  await signIn(page, "rahul@example.com", "Seeker@123");
  await caption(page, "Job seeker: search with typo correction and synonyms");
  const box = page.getByRole("combobox", { name: /search jobs/i });
  await box.fill("pyhton backend");
  await box.press("Enter");
  await expect(page.getByText("Showing results for")).toBeVisible();
  await caption(page, "\"pyhton\" is corrected to \"python\"; every job shows a match score");
  await page.getByRole("list", { name: "Jobs" }).getByRole("link").first().click();
  await page.getByText("How this score is calculated").click();
  await caption(page, "Every part of the score is shown: points, weight and the reason", 3200);
  await page.goto("/applications");
  await caption(page, "Applications with a status timeline and upcoming interviews");
  await page.goto("/resume");
  await caption(page, "Resumes: consent first, malware screening, encrypted storage, delete any time", 3000);
  await signOut(page, "Rahul Verma");

  // ---- recruiter ----
  await signIn(page, "rohan@example.com", "Recruiter@123");
  await caption(page, "Recruiter: pipeline board with keyboard-accessible drag and drop");
  await page.getByRole("tab", { name: "Ranked list" }).click();
  await page.getByRole("button", { name: /^Why / }).first().click();
  await caption(page, "Candidates ranked by fit, with the reasons; the score is decision support", 3200);
  await page.getByRole("tab", { name: "Pipeline" }).click();
  const interviewCol = page.getByRole("region", { name: /^Interview column/ });
  const actions = interviewCol.getByRole("button", { name: /^Actions for / });
  if ((await actions.count()) > 0) {
    await actions.first().click();
    await page.getByRole("menuitem", { name: "Schedule interview" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Meeting link or number").fill("https://meet.example.com/demo");
    await caption(page, "Scheduling an interview sends an email with a calendar invite", 2400);
    await dialog.getByRole("button", { name: "Schedule and send invite" }).click();
    await page.waitForTimeout(1200);
  }
  await page.goto("/recruiter/analytics");
  await caption(page, "Analytics: hiring funnel, conversion, time to first response and to offer", 3200);
  await signOut(page, "Rohan Kapoor");

  // ---- admin ----
  await signIn(page, "admin@example.com", "Admin@123");
  await page.goto("/admin/system");
  await caption(page, "Admin: dependency health, background tasks and dead-letter retries", 3000);
  await page.goto("/admin/audit");
  await caption(page, "Audit log of sign-ins, admin actions, pipeline moves and resume access", 3000);
  await caption(page, "github.com/Saipavanavsp/hike", 2500);

  await page.close();
  const video = page.video();
  if (video) {
    const out = path.resolve(__dirname, "../../docs/demo");
    mkdirSync(out, { recursive: true });
    copyFileSync(await video.path(), path.join(out, "hike-demo.webm"));
    testInfo.annotations.push({ type: "video", description: path.join(out, "hike-demo.webm") });
  }
});
