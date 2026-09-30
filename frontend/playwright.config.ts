import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run against the dev stack only: the LMS Flask API on :5060 (nipunalms-dev, seeded with the
 * staging users) and Vite on :5174. Start both first (see docs/FRONTEND_PLAN.md).
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: process.env["E2E_BASE_URL"] ?? "http://localhost:5174", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "mobile", use: { ...devices["Pixel 7"] }, grep: /@mobile/ },
  ],
});
