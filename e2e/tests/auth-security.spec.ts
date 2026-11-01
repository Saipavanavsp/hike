import { expect, test } from "@playwright/test";
import {
  ADMIN,
  apiLogin,
  login,
  RECRUITER,
  refreshCookieFrom,
  registerSeeker,
} from "./helpers";

test.describe("authentication and access control", () => {
  test("invalid login shows an error and stays on the login page", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("nobody-here@example.com");
    await page.getByLabel("Password").fill("WrongPass123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Incorrect email or password")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);

    // Right email, wrong password: same message (no account enumeration).
    await page.getByLabel("Email").fill(RECRUITER.email);
    await page.getByLabel("Password").fill("NotThePassword1");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Incorrect email or password")).toBeVisible();
  });

  test("protected pages redirect by role", async ({ page, browser }) => {
    // Anonymous: sent to login, remembering where they were going.
    await page.goto("/resume");
    await expect(page).toHaveURL(/\/login\?next=%2Fresume/);

    // A recruiter cannot open admin or seeker pages.
    const recCtx = await browser.newContext();
    const rp = await recCtx.newPage();
    await login(rp, RECRUITER.email, RECRUITER.password);
    await rp.goto("/admin/users");
    await expect(rp).toHaveURL(/\/recruiter$/);
    await rp.goto("/resume");
    await expect(rp).toHaveURL(/\/recruiter$/);
    await recCtx.close();
  });

  test("API enforces 401 for anonymous and 403 for the wrong role", async ({ request }) => {
    const seeker = await registerSeeker(request, "rbac");
    const recruiter = await apiLogin(request, RECRUITER.email, RECRUITER.password);
    const admin = await apiLogin(request, ADMIN.email, ADMIN.password);

    for (const path of ["/api/admin/users", "/api/admin/system", "/api/recruiter/jobs"]) {
      expect((await request.get(path)).status(), path).toBe(401);
    }
    expect((await request.get("/api/admin/users", { headers: seeker.auth })).status()).toBe(403);
    expect((await request.get("/api/admin/system", { headers: recruiter })).status()).toBe(403);
    expect(
      (await request.post("/api/admin/users/deactivate", { headers: recruiter, data: { ids: [1] } }))
        .status(),
    ).toBe(403);
    expect((await request.get("/api/recruiter/jobs", { headers: seeker.auth })).status()).toBe(403);
    expect((await request.get("/api/resumes", { headers: recruiter })).status()).toBe(403);
    expect((await request.get("/api/admin/users", { headers: admin })).status()).toBe(200);

    // A forged token is rejected, not treated as anonymous.
    const forged = { Authorization: "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.forged" };
    expect((await request.get("/api/auth/me", { headers: forged })).status()).toBe(401);
  });

  test("admin cannot deactivate their own account", async ({ request }) => {
    const admin = await apiLogin(request, ADMIN.email, ADMIN.password);
    const me = await (await request.get("/api/auth/me", { headers: admin })).json();
    const res = await request.post("/api/admin/users/deactivate", {
      headers: admin,
      data: { ids: [me.id] },
    });
    expect(res.status()).toBe(422);
  });

  test("reusing a rotated refresh token revokes the whole session", async ({ playwright, baseURL }) => {
    const ctx = await playwright.request.newContext({ baseURL });
    const seeker = await registerSeeker(ctx, "refresh");
    const loginRes = await ctx.post("/api/auth/login", {
      data: { email: seeker.email, password: seeker.password },
    });
    const original = refreshCookieFrom(
      loginRes.headersArray().filter((h) => h.name.toLowerCase() === "set-cookie").map((h) => h.value),
    );
    await ctx.dispose();

    // Each call uses a fresh context so only the cookie we pass is sent.
    async function refresh(token: string) {
      const c = await playwright.request.newContext({ baseURL });
      const res = await c.post("/api/auth/refresh", { headers: { Cookie: `hike_refresh=${token}` } });
      const status = res.status();
      const cookies = res
        .headersArray()
        .filter((h) => h.name.toLowerCase() === "set-cookie")
        .map((h) => h.value);
      await c.dispose();
      return { status, cookies };
    }

    const first = await refresh(original);
    expect(first.status).toBe(200);
    const rotated = refreshCookieFrom(first.cookies);
    expect(rotated).not.toBe(original);

    // Replaying the old token is treated as theft...
    expect((await refresh(original)).status).toBe(401);
    // ...so the token the legitimate client holds is revoked too.
    expect((await refresh(rotated)).status).toBe(401);
  });

  test("signing out revokes the refresh token", async ({ browser, request, playwright, baseURL }) => {
    const seeker = await registerSeeker(request, "logout");
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await login(page, seeker.email, seeker.password);
    const cookie = (await ctx.cookies()).find((c) => c.name === "hike_refresh");
    expect(cookie?.httpOnly).toBe(true);

    await page.getByRole("button", { name: seeker.name }).click();
    await page.getByRole("menuitem", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/login/);

    const replay = await playwright.request.newContext({ baseURL });
    const res = await replay.post("/api/auth/refresh", {
      headers: { Cookie: `hike_refresh=${cookie!.value}` },
    });
    expect(res.status()).toBe(401);
    await replay.dispose();
    await ctx.close();
  });

  test("deactivation ends an active browser session", async ({ browser, request }) => {
    const seeker = await registerSeeker(request, "session");
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await login(page, seeker.email, seeker.password);
    await expect(page).toHaveURL(/\/jobs/);

    // Reload keeps the session (refresh cookie)...
    await page.reload();
    await expect(page).toHaveURL(/\/jobs/);

    // ...until an admin deactivates the account: sessions are revoked immediately.
    const admin = await apiLogin(request, ADMIN.email, ADMIN.password);
    const me = await (await request.get("/api/auth/me", { headers: seeker.auth })).json();
    const res = await request.post("/api/admin/users/deactivate", {
      headers: admin,
      data: { ids: [me.id] },
    });
    expect((await res.json()).updated).toBe(1);
    expect((await request.get("/api/auth/me", { headers: seeker.auth })).status()).toBe(401);

    await page.reload();
    await expect(page).toHaveURL(/\/login/);
    await page.getByLabel("Email").fill(seeker.email);
    await page.getByLabel("Password").fill(seeker.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("This account has been deactivated")).toBeVisible();
    await ctx.close();
  });
});
