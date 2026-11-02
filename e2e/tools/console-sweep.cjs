// Visit every page as each role and report console errors (CSP violations show up there).
const { chromium } = require("@playwright/test");
const BASE = process.argv[2] || "http://localhost:8080";
const ROLES = {
  seeker: ["rahul@example.com", "Seeker@123", ["/jobs", "/jobs/1", "/applications", "/saved", "/profile", "/resume", "/companies/nimbus-ledger"]],
  recruiter: ["rohan@example.com", "Recruiter@123", ["/recruiter", "/recruiter/jobs", "/recruiter/jobs/new", "/recruiter/interviews", "/recruiter/analytics", "/recruiter/company"]],
  admin: ["admin@example.com", "Admin@123", ["/admin/users", "/admin/jobs", "/admin/applications", "/admin/system", "/admin/audit"]],
};
(async () => {
  const b = await chromium.launch();
  const problems = [];
  let pages = 0;
  for (const [role, [email, pw, paths]] of Object.entries(ROLES)) {
    const p = await (await b.newContext()).newPage();
    p.on("console", (m) => m.type() === "error" && problems.push(`${role} ${p.url()}: ${m.text()}`));
    p.on("pageerror", (e) => problems.push(`${role} ${p.url()}: ${e.message}`));
    await p.goto(`${BASE}/login`);
    await p.getByLabel("Email").fill(email);
    await p.getByLabel("Password").fill(pw);
    await p.getByRole("button", { name: "Sign in" }).click();
    await p.waitForURL((u) => !u.pathname.startsWith("/login"));
    for (const path of paths) {
      await p.goto(BASE + path);
      await p.waitForLoadState("networkidle");
      pages++;
    }
  }
  console.log(`pages visited: ${pages}; console errors: ${problems.length ? "\n" + problems.join("\n") : "none"}`);
  await b.close();
})();
