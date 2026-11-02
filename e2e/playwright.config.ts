import { defineConfig, devices } from "@playwright/test";

// Runs against the docker-compose stack by default (nginx on :8080 proxying /api).
export default defineConfig({
  testDir: "./tests",
  testIgnore: ["**/screenshots.spec.ts"],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    trace: "retain-on-failure",
    // API calls made by the tests carry the CSRF header the frontend sends.
    extraHTTPHeaders: { "X-CSRF-Protection": "1" },
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
