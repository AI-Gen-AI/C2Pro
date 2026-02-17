import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";

export default defineConfig({
  testDir: "./src/tests/e2e",
  fullyParallel: true,
  retries: 0,
  reporter: "list",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  // webServer disabled - using existing dev server on port 3000
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "e2e-j2-weekly-review",
      testMatch: /journey-2-review\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
      metadata: {
        suite: "TS-E2E-J2-001",
        phase: "red",
        type: "e2e",
        priority: "p0",
        description: "Weekly Project Review Journey",
      },
    },
  ],
});
