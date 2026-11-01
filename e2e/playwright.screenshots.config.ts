import { defineConfig, devices } from "@playwright/test";

// `npm run screenshots`: captures real screens of a running stack for the README and landing page.
export default defineConfig({
  testDir: "./tests",
  testMatch: ["**/screenshots.spec.ts"],
  timeout: 120_000,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
