import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100";
const useManagedWebServer = process.env.PLAYWRIGHT_SKIP_WEBSERVER !== "1";

export default defineConfig({
  testDir: "./src/tests/e2e",
  fullyParallel: true,
  retries: 0,
  reporter: "list",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  webServer: useManagedWebServer
    ? {
        command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
        url: `${baseURL}/demo/evidence`,
        reuseExistingServer: true,
        timeout: 120_000,
      }
    : undefined,
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "visual-regression",
      testMatch: /core-pages\.visual\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1200 },
        colorScheme: "light",
        locale: "en-US",
        timezoneId: "UTC",
      },
      metadata: {
        task: "TASK-021",
        type: "visual-regression",
        scope: "core-pages",
      },
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
