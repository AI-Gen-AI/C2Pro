/**
 * Test Suite ID: TASK-1429
 * Backlog Task: TASK-1429
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("TASK-1429 RED - localhost Playwright dev server", () => {
  it("[TASK-1429-RED-01] uses localhost as the Playwright base URL to avoid the 127.0.0.1 self-proxy failure in Next dev", () => {
    const configPath = resolve(process.cwd(), "playwright.config.ts");
    const config = readFileSync(configPath, "utf8");

    expect(config).toContain('const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3100"');
    expect(config).toContain('command: "npm run dev -- --hostname localhost --port 3100 --webpack"');
  });
});
