/**
 * Manual, read-only production identity qualification.
 * No local web server, persistent storageState, recording, or application writes.
 * Distinct from the localhost development Nightly and from production mutation.
 */
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./src/tests/e2e",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: "https://c2pro.io",
    trace: "off",
    screenshot: "off",
    video: "off",
    ...devices["Desktop Chrome"],
  },
  projects: [
    {
      name: "prod-s1-clerk-setup",
      testMatch: /acc01-s1-clerk-production\.setup\.ts$/,
    },
    {
      name: "prod-s1-identity-readonly",
      testMatch: /acc01-s1-clerk-production-readonly\.spec\.ts$/,
      dependencies: ["prod-s1-clerk-setup"],
    },
  ],
});
