import { expect, test } from "@playwright/test";
import {
  apiLogin,
  giveResume,
  jobIdByTitle,
  login,
  OTHER_RECRUITER,
  RECRUITER,
  registerSeeker,
  ROHAN_JOB,
} from "./helpers";

test.describe("application rules", () => {
  test("a seeker cannot apply twice to the same job", async ({ page, request }) => {
    const seeker = await registerSeeker(request, "dup");
    await giveResume(request, seeker.auth);
    const jobId = await jobIdByTitle(request, ROHAN_JOB);

    const first = await request.post("/api/applications", {
      headers: seeker.auth,
      data: { job_id: jobId },
    });
    expect(first.status()).toBe(201);
    const second = await request.post("/api/applications", {
      headers: seeker.auth,
      data: { job_id: jobId },
    });
    expect(second.status()).toBe(409);
    expect((await second.json()).detail).toBe("You have already applied to this job");

    // The job page shows the existing application instead of an Apply button.
    await login(page, seeker.email, seeker.password);
    await page.goto(`/jobs/${jobId}`);
    await expect(page.getByText("Application status")).toBeVisible();
    await expect(page.getByRole("button", { name: "Apply", exact: true })).toHaveCount(0);
  });

  test("a seeker without a resume cannot apply", async ({ request }) => {
    const seeker = await registerSeeker(request, "noresume");
    const jobId = await jobIdByTitle(request, ROHAN_JOB);
    const res = await request.post("/api/applications", {
      headers: seeker.auth,
      data: { job_id: jobId },
    });
    expect(res.status()).toBe(422);
  });

  test("invalid pipeline moves are refused, and only the job's recruiter can move", async ({
    page,
    request,
  }) => {
    const seeker = await registerSeeker(request, "pipeline");
    await giveResume(request, seeker.auth);
    const jobId = await jobIdByTitle(request, ROHAN_JOB);
    const app = await (
      await request.post("/api/applications", { headers: seeker.auth, data: { job_id: jobId } })
    ).json();
    const rohan = await apiLogin(request, RECRUITER.email, RECRUITER.password);
    const meera = await apiLogin(request, OTHER_RECRUITER.email, OTHER_RECRUITER.password);
    const move = (auth: object, status: string) =>
      request.patch(`/api/recruiter/applications/${app.id}/status`, {
        headers: auth as Record<string, string>,
        data: { status },
      });

    // Skipping stages is not allowed.
    const skip = await move(rohan, "offer");
    expect(skip.status()).toBe(422);
    expect((await skip.json()).detail).toBe("Cannot move from Applied to Offer");
    expect((await move(rohan, "interview")).status()).toBe(422);

    // Another company's recruiter cannot see or move this candidate; neither can the seeker.
    expect((await move(meera, "shortlisted")).status()).toBe(403);
    expect(
      (await request.get(`/api/recruiter/jobs/${jobId}/applications`, { headers: meera })).status(),
    ).toBe(403);
    expect((await move(seeker.auth, "shortlisted")).status()).toBe(403);

    // A valid move still works, and the UI only offers valid moves.
    expect((await move(rohan, "shortlisted")).status()).toBe(200);
    await login(page, RECRUITER.email, RECRUITER.password);
    await page.goto(`/recruiter/jobs/${jobId}`);
    await page.getByRole("button", { name: `Actions for ${seeker.name}` }).click();
    await expect(page.getByRole("menuitem", { name: "Move to Interview" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Move to Offer" })).toHaveCount(0);
    await page.keyboard.press("Escape");
  });
});
