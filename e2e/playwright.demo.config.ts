import { defineConfig, devices } from "@playwright/test";

// Records docs/demo/hike-demo.webm:  npx playwright test --config playwright.demo.config.ts
export default defineConfig({
  testDir: "./tests",
  testMatch: ["**/demo.spec.ts"],
  timeout: 240_000,
  expect: { timeout: 15_000 },
  reporter: "list",
  outputDir: "demo-results",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    extraHTTPHeaders: { "X-CSRF-Protection": "1" },
    video: { mode: "on", size: { width: 1280, height: 720 } },
    launchOptions: { slowMo: 120 },
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 720 } } },
  ],
});
