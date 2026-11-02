// Post-deploy smoke test against a running Hike (no browser needed):
//   node e2e/tools/smoke.cjs http://localhost:8080
//   node e2e/tools/smoke.cjs https://hike-web.onrender.com
// Exercises the critical path (health, search, sign-in, resume upload -> worker parse ->
// encrypted storage -> signed download, recruiter pipeline, admin system page) and exits
// non-zero on the first failure. Set SMOKE_EMAIL to reuse an account across runs
// (to prove data survived a restart); otherwise a new seeker is registered.
const fs = require("node:fs");
const path = require("node:path");

const BASE = (process.argv[2] || "http://localhost:8080").replace(/\/$/, "");
const CSRF = { "X-CSRF-Protection": "1" };
const PDF = fs.readFileSync(path.join(__dirname, "../../backend/tests/fixtures/priya_sharma_backend.pdf"));
const results = [];

async function step(name, fn) {
  const t0 = Date.now();
  try {
    const detail = await fn();
    results.push({ name, ok: true, ms: Date.now() - t0, detail });
    console.log(`  ok   ${name} (${Date.now() - t0} ms)${detail ? ` ${detail}` : ""}`);
  } catch (e) {
    console.log(`  FAIL ${name}: ${e.message}`);
    console.log(`\nsmoke test FAILED at "${name}" against ${BASE}`);
    process.exit(1);
  }
}

async function call(method, url, { headers = {}, json, body, expect = 200 } = {}) {
  const res = await fetch(BASE + url, {
    method,
    headers: { ...(json ? { "Content-Type": "application/json" } : {}), ...headers },
    body: json ? JSON.stringify(json) : body,
  });
  const expected = Array.isArray(expect) ? expect : [expect];
  if (!expected.includes(res.status)) {
    throw new Error(`${method} ${url} -> ${res.status} ${(await res.text()).slice(0, 200)}`);
  }
  return res;
}

async function login(email, password) {
  const r = await call("POST", "/api/auth/login", { json: { email, password }, headers: CSRF });
  return { Authorization: `Bearer ${(await r.json()).access_token}` };
}

(async () => {
  console.log(`smoke test against ${BASE}`);
  let seeker;
  let jobId;
  let resumeId;

  await step("API health (db + redis)", async () => {
    const h = await (await call("GET", "/api/health")).json();
    if (h.db !== "ok" || h.redis !== "ok") throw new Error(JSON.stringify(h));
    return `worker=${h.worker}, queue=${h.queue_depth}`;
  });
  await step("frontend and security headers", async () => {
    const r = await call("GET", "/login");
    const csp = r.headers.get("content-security-policy") || "";
    if (!csp.includes("script-src 'self'")) throw new Error("missing CSP");
    return "CSP present";
  });
  await step("search (typo corrected)", async () => {
    const page = await (await call("GET", "/api/jobs?q=pyhton")).json();
    if (!page.items.length) throw new Error("no results");
    jobId = page.items[0].id;
    return `${page.total} jobs, corrected to "${page.corrected_query}"`;
  });
  await step("seeker account", async () => {
    const email = process.env.SMOKE_EMAIL;
    if (email) {
      seeker = await login(email, process.env.SMOKE_PASSWORD || "SmokeTest123");
      return `signed in as existing ${email}`;
    }
    const fresh = `smoke-${Date.now().toString(36)}@example.com`;
    const r = await call("POST", "/api/auth/register", {
      json: { email: fresh, password: "SmokeTest123", full_name: "Smoke Test", role: "seeker" },
      headers: CSRF,
      expect: 201,
    });
    seeker = { Authorization: `Bearer ${(await r.json()).access_token}` };
    return `registered ${fresh}`;
  });
  if (process.env.SMOKE_EMAIL) {
    await step("resume uploaded before the restart is still readable", async () => {
      const list = await (await call("GET", "/api/resumes", { headers: seeker })).json();
      if (!list.length) throw new Error("account has no earlier resumes");
      const oldest = list[list.length - 1];
      const link = await (await call("POST", `/api/resumes/${oldest.id}/link`, { headers: seeker })).json();
      const bytes = Buffer.from(await (await call("GET", link.url)).arrayBuffer());
      if (!bytes.equals(PDF)) throw new Error("stored file changed or unreadable");
      return `resume ${oldest.id} from ${oldest.created_at} decrypts to the original`;
    });
  }
  await step("resume upload, parsed by the worker", async () => {
    const form = new FormData();
    form.append("file", new Blob([PDF], { type: "application/pdf" }), "smoke.pdf");
    form.append("consent", "true");
    const r = await call("POST", "/api/resumes", { body: form, headers: seeker, expect: 202 });
    resumeId = (await r.json()).id;
    for (let i = 0; i < 60; i++) {
      const s = (await (await call("GET", `/api/resumes/${resumeId}`, { headers: seeker })).json()).status;
      if (s === "ready") return `resume ${resumeId} ready after ~${i}s`;
      if (s === "failed") throw new Error("parse failed");
      await new Promise((res) => setTimeout(res, 1000));
    }
    throw new Error("still processing after 60 s (is the worker running?)");
  });
  await step("signed download decrypts the stored file", async () => {
    const link = await (await call("POST", `/api/resumes/${resumeId}/link`, { headers: seeker })).json();
    const file = await call("GET", link.url);
    const bytes = Buffer.from(await file.arrayBuffer());
    if (!bytes.subarray(0, 5).equals(Buffer.from("%PDF-"))) throw new Error("not the original PDF");
    if (!bytes.equals(PDF)) throw new Error("content differs from upload");
    return `${bytes.length} bytes match the upload`;
  });
  await step("job detail with score breakdown", async () => {
    await call("PUT", `/api/resumes/${resumeId}`, { headers: seeker, json: { skills: ["Python", "FastAPI"] } });
    const job = await (await call("GET", `/api/jobs/${jobId}`, { headers: seeker })).json();
    if (!job.match || job.match.components.length !== 4) throw new Error("no breakdown");
    return `match ${job.match.score}`;
  });
  await step("recruiter pipeline", async () => {
    const h = await login("rohan@example.com", "Recruiter@123");
    const jobs = await (await call("GET", "/api/recruiter/jobs", { headers: h })).json();
    const busiest = jobs.sort((a, b) => b.applications_count - a.applications_count)[0];
    const apps = await (await call("GET", `/api/recruiter/jobs/${busiest.id}/applications`, { headers: h })).json();
    return `${apps.length} candidates ranked`;
  });
  await step("admin system page", async () => {
    const h = await login("admin@example.com", "Admin@123");
    const s = await (await call("GET", "/api/admin/system", { headers: h })).json();
    if (!s.dependencies.postgres.ok || !s.dependencies.redis.ok) throw new Error(JSON.stringify(s.dependencies));
    return `worker=${s.worker}, dead letter=${s.dead_letter}`;
  });
  await step("access control: anonymous is refused", async () => {
    await call("GET", "/api/admin/users", { expect: 401 });
    await call("GET", "/api/admin/users", { headers: seeker, expect: 403 });
  });
  console.log(`\nsmoke test PASSED: ${results.length} checks against ${BASE}`);
})();
