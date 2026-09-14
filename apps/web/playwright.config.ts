import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3100";
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
        command: "pnpm dev --hostname localhost --port 3100 --webpack",
        url: baseURL,
        reuseExistingServer: false,
        timeout: 120_000,
      }
    : undefined,
  projects: [
    {
      name: "global-setup",
      testMatch: /global\.setup\.ts/,
    },
    {
      name: "setup",
      testMatch: /auth\.setup\.ts/,
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["global-setup"],
    },
    {
      name: "chromium",
      // The P0b specs sign in live in their own context; restoring a session
      // under them would both mask the variable under investigation and collide
      // with the ticket sign-in.
      testIgnore: [
        /p0b-single-document-health\.spec\.ts/,
        /auth-continuity\.spec\.ts/,
        // Anchored to the file name: matching runs against the absolute path, and a checkout
        // directory may itself contain "pj01-".
        /(^|[\\/])pj01-[^\\/]*\.spec\.ts$/,
      ],
      use: {
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/user.json",
      },
      dependencies: ["setup"],
    },
    {
      // PJ-01 First Real User Journey. Like P0b: NO storageState — the journey performs the
      // documented Clerk bootstrap itself and needs global-setup for the testing token.
      name: "pj01-acceptance",
      testMatch: [/(^|[\\/])pj01-[^\\/]*\.spec\.ts$/],
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["global-setup"],
      metadata: {
        suite: "TS-E2E-PJ01-001",
        type: "e2e",
        priority: "p0",
        description: "PJ-01 first real user journey (shared harness, first half)",
      },
    },
    {
      // Canonical P0b acceptance. NO storageState: the journey performs the
      // documented Clerk bootstrap itself, in the same page and context it then
      // gates and continues into. It still needs global-setup, which fetches the
      // Clerk testing token that the development instance requires.
      name: "p0b-acceptance",
      testMatch: [/p0b-single-document-health\.spec\.ts/, /auth-continuity\.spec\.ts/],
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["global-setup"],
      metadata: {
        suite: "TS-E2E-P0B-HEALTH-001",
        type: "e2e",
        priority: "p0",
        description: "Single-document Health journey with inline auth gate",
      },
    },
    {
      name: "cross-browser-chromium",
      testMatch: /cross-browser-smoke\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
      metadata: {
        task: "TASK-024",
        type: "cross-browser-smoke",
        browser: "chromium",
      },
    },
    {
      name: "cross-browser-firefox",
      testMatch: /cross-browser-smoke\.spec\.ts/,
      use: { ...devices["Desktop Firefox"] },
      metadata: {
        task: "TASK-024",
        type: "cross-browser-smoke",
        browser: "firefox",
      },
    },
    {
      name: "cross-browser-webkit",
      testMatch: /cross-browser-smoke\.spec\.ts/,
      use: { ...devices["Desktop Safari"] },
      metadata: {
        task: "TASK-024",
        type: "cross-browser-smoke",
        browser: "webkit",
      },
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
      use: { 
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/user.json",
      },
      dependencies: ["setup"],
      metadata: {
        suite: "TS-E2E-J2-001",
        phase: "red",
        type: "e2e",
        priority: "p0",
        description: "Weekly Project Review Journey",
      },
    },
    {
      name: "e2e-document-analysis-pipeline",
      testMatch: /document-analysis-pipeline\.spec\.ts/,
      use: { 
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/user.json",
      },
      dependencies: ["setup"],
      metadata: {
        suite: "TS-E2E-DAP-001",
        phase: "green",
        type: "e2e",
        priority: "p1",
        task: "TASK-FRT-166",
        description: "Document Analysis Pipeline Journey",
      },
    },
  ],
});
