import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import {
  apiLogin,
  giveResume,
  jobIdByTitle,
  login,
  RECRUITER,
  RESUME_PDF,
  registerSeeker,
  ROHAN_JOB,
} from "./helpers";

// The standard anti-virus test signature (harmless by design).
const EICAR = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*";

async function openResumePage(page: Page, email: string, password: string) {
  await login(page, email, password);
  await page.goto("/resume");
  await page.getByRole("checkbox", { name: /I agree that Hike may scan/ }).check();
}

async function choose(page: Page, name: string, mimeType: string, buffer: Buffer) {
  await page.getByLabel("Resume file").setInputFiles({ name, mimeType, buffer });
}

test.describe("resume upload failures", () => {
  test("each kind of bad file gets a clear message and nothing is saved", async ({
    page,
    request,
  }) => {
    const seeker = await registerSeeker(request, "badfile");
    await login(page, seeker.email, seeker.password);
    await page.goto("/resume");

    // No consent: the file picker is disabled.
    await expect(page.getByRole("button", { name: "Choose file" })).toBeDisabled();
    await page.getByRole("checkbox", { name: /I agree that Hike may scan/ }).check();
    await expect(page.getByRole("button", { name: "Choose file" })).toBeEnabled();

    // Wrong type and oversize are caught before upload.
    await choose(page, "notes.txt", "text/plain", Buffer.from("hello"));
    await expect(page.getByRole("alert")).toHaveText("Choose a PDF or DOCX file.");
    await choose(page, "huge.pdf", "application/pdf", Buffer.alloc(6 * 1024 * 1024, 48));
    await expect(page.getByRole("alert")).toContainText("The limit is 5 MB.");

    // A renamed non-PDF is rejected by the server's magic-byte check.
    await choose(page, "fake.pdf", "application/pdf", Buffer.from("this is not a pdf at all"));
    await expect(page.getByRole("alert")).toHaveText("File is not a valid PDF");

    // Malware screening rejects the EICAR test file at upload time.
    await choose(page, "eicar.pdf", "application/pdf", Buffer.from(`%PDF-1.4\n${EICAR}\n%%EOF`));
    await expect(page.getByRole("alert")).toHaveText("This file was blocked by the security scan");

    // A PDF the sandboxed parser cannot read fails in the background worker.
    await choose(page, "broken.pdf", "application/pdf", Buffer.from("%PDF-1.4\nbroken body\n%%EOF"));
    await expect(page.getByText(/Could not read text from this file.*Try another file/)).toBeVisible({
      timeout: 30_000,
    });

    // Only the broken-but-safe upload was stored, marked as failed, and the API agrees.
    const resumes = await (await request.get("/api/resumes", { headers: seeker.auth })).json();
    expect(resumes.map((r: { status: string }) => r.status)).toEqual(["failed"]);
  });

  test("upload without consent is refused by the API", async ({ request }) => {
    const seeker = await registerSeeker(request, "noconsent");
    const res = await request.post("/api/resumes", {
      headers: seeker.auth,
      multipart: {
        file: { name: "cv.pdf", mimeType: "application/pdf", buffer: readFileSync(RESUME_PDF) },
      },
    });
    expect(res.status()).toBe(422);
  });
});

test.describe("resume privacy", () => {
  test("upload, view through an expiring link, delete the resume, delete the account", async ({
    page,
    context,
    request,
  }) => {
    const seeker = await registerSeeker(request, "privacy");
    await openResumePage(page, seeker.email, seeker.password);

    // Parsed by the background worker, then reviewed and saved.
    await choose(page, "my-resume.pdf", "application/pdf", readFileSync(RESUME_PDF));
    await expect(page.getByText("Review: my-resume.pdf")).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: "Save resume" }).click();
    await expect(page.getByText("Resume saved")).toBeVisible();
    await expect(page.getByText("Current resume")).toBeVisible();

    // "View file" opens a signed, short-lived link that works without the bearer token.
    // (Headless Chromium downloads PDFs instead of showing them, so watch the request.)
    const opened = context.waitForEvent("request", (r) => r.url().includes("/api/files/resumes/"));
    await page.getByRole("button", { name: "View file" }).click();
    const signedUrl = (await opened).url();
    expect(signedUrl).toMatch(/\/api\/files\/resumes\/\d+\?uid=\d+&exp=\d+&sig=[0-9a-f]{64}$/);
    for (const p of context.pages()) if (p !== page) await p.close();
    const file = await request.get(signedUrl);
    expect(file.status()).toBe(200);
    expect(file.headers()["content-type"]).toBe("application/pdf");
    expect(file.headers()["cache-control"]).toBe("private, no-store");
    // Tampering with the link breaks it.
    expect((await request.get(signedUrl.replace(/sig=.{4}/, "sig=0000"))).status()).toBe(403);

    // Delete the resume: the file and its data are gone, and so is the link.
    await page.getByRole("button", { name: "Delete", exact: true }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Delete permanently" }).click();
    await expect(page.getByText("Resume deleted")).toBeVisible();
    await expect(page.getByText("Current resume")).toHaveCount(0);
    expect((await request.get(signedUrl)).status()).toBe(404);

    // Delete the account from the profile page (password required).
    await page.goto("/profile");
    await page.getByRole("button", { name: "Delete my account" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Enter your password to confirm").fill("wrong-password");
    await dialog.getByRole("button", { name: "Delete everything" }).click();
    await expect(dialog.getByText("Password is incorrect")).toBeVisible();
    await dialog.getByLabel("Enter your password to confirm").fill(seeker.password);
    await dialog.getByRole("button", { name: "Delete everything" }).click();
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByText("Your account and data have been deleted")).toBeVisible();

    const relogin = await request.post("/api/auth/login", {
      data: { email: seeker.email, password: seeker.password },
    });
    expect(relogin.status()).toBe(401);
  });

  test("a recruiter sees an application whose resume was deleted, without the resume", async ({
    request,
  }) => {
    const seeker = await registerSeeker(request, "deleted");
    const resumeId = await giveResume(request, seeker.auth);
    const jobId = await jobIdByTitle(request, ROHAN_JOB);
    await request.post("/api/applications", { headers: seeker.auth, data: { job_id: jobId } });
    expect(
      (await request.delete(`/api/resumes/${resumeId}`, { headers: seeker.auth })).status(),
    ).toBe(204);

    const rohan = await apiLogin(request, RECRUITER.email, RECRUITER.password);
    const rows = await (
      await request.get(`/api/recruiter/jobs/${jobId}/applications`, { headers: rohan })
    ).json();
    const row = rows.find((r: { candidate: { email: string } }) => r.candidate.email === seeker.email);
    expect(row.resume).toBeNull();
    expect(row.match).toBeNull();
    expect((await request.post(`/api/resumes/${resumeId}/link`, { headers: rohan })).status()).toBe(
      404,
    );
  });
});
