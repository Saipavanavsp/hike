import { expect, test } from "@playwright/test";
import path from "node:path";
import { login } from "./helpers";

// Real screenshots of the running app for the README and the landing page browser frame.
const ROOT = path.resolve(__dirname, "../..");
const DOCS = path.join(ROOT, "docs", "screenshots");
const PUBLIC = path.join(ROOT, "frontend", "public", "screenshots");

test("capture screenshots", async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  await login(page, "rahul@example.com", "Seeker@123");
  await expect(page.getByRole("list", { name: "Jobs" })).toBeVisible();
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(PUBLIC, "seeker-dashboard.png") });
  await page.screenshot({ path: path.join(DOCS, "seeker-dashboard.png") });

  await page.getByRole("link", { name: "Backend Engineer (Python)" }).click();
  await expect(page.getByLabel("Match breakdown")).toBeVisible();
  await page.screenshot({ path: path.join(DOCS, "job-detail.png") });
  await page.goto("/resume");
  await expect(page.getByText("Current resume")).toBeVisible();
  await page.screenshot({ path: path.join(DOCS, "resume.png") });
  await ctx.clearCookies();
  await page.evaluate(() => localStorage.clear());

  await login(page, "meera@example.com", "Recruiter@123");
  await expect(page.getByTestId("kanban")).toBeVisible();
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(DOCS, "recruiter-pipeline.png") });
  await page.getByRole("tab", { name: "Ranked list" }).click();
  await page.screenshot({ path: path.join(DOCS, "recruiter-ranked.png") });
  await ctx.clearCookies();
  await page.evaluate(() => localStorage.clear());

  await login(page, "admin@example.com", "Admin@123");
  await expect(page.getByRole("table")).toBeVisible();
  await page.screenshot({ path: path.join(DOCS, "admin-users.png") });

  await page.goto("/login");
  await ctx.clearCookies();
  await page.evaluate(() => localStorage.clear());
  await page.goto("/login");
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(DOCS, "landing.png"), fullPage: true });

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const mp = await mobile.newPage();
  await login(mp, "rahul@example.com", "Seeker@123");
  await expect(mp.getByRole("list", { name: "Jobs" })).toBeVisible();
  await mp.screenshot({ path: path.join(DOCS, "mobile-jobs.png") });

  await ctx.close();
  await mobile.close();
});
