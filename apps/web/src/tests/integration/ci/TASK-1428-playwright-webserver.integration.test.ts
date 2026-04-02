/**
 * Test Suite ID: TASK-1428
 * Backlog Task: TASK-1428
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("TASK-1428 RED - Playwright managed web server stability", () => {
  it("[TASK-1428-RED-01] forces the Playwright webServer lane to start Next with webpack", () => {
    const configPath = resolve(process.cwd(), "playwright.config.ts");
    const config = readFileSync(configPath, "utf8");

    expect(config).toContain("--webpack");
  });

  it("[TASK-1428-RED-02] pins the Next turbopack root to the app workspace to avoid wrong monorepo inference", () => {
    const configPath = resolve(process.cwd(), "next.config.js");
    const config = readFileSync(configPath, "utf8");

    expect(config).toContain("turbopack:");
    expect(config).toContain("root: __dirname");
  });

  it("[TASK-1428-RED-03] probes a stable public route for Playwright webServer readiness instead of a heavy demo page", () => {
    const configPath = resolve(process.cwd(), "playwright.config.ts");
    const config = readFileSync(configPath, "utf8");

    expect(config).toContain("url: baseURL");
    expect(config).not.toContain('url: `${baseURL}/demo/evidence`');
  });

  it("[TASK-1428-RED-04] disables webServer reuse so cross-browser runs cannot attach to a stale local dev process", () => {
    const configPath = resolve(process.cwd(), "playwright.config.ts");
    const config = readFileSync(configPath, "utf8");

    expect(config).toContain("reuseExistingServer: false");
  });
});
