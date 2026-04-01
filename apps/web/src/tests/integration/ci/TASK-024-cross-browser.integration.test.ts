/**
 * Test Suite ID: TASK-024
 * Backlog Task: TASK-024
 */
import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("TASK-024 RED - cross-browser coverage", () => {
  it("[TASK-024-RED-01] defines dedicated cross-browser Playwright projects for Chromium, Firefox, and WebKit", () => {
    const configPath = resolve(process.cwd(), "playwright.config.ts");
    const config = readFileSync(configPath, "utf8");

    expect(config).toContain('name: "cross-browser-chromium"');
    expect(config).toContain('name: "cross-browser-firefox"');
    expect(config).toContain('name: "cross-browser-webkit"');
    expect(config).toContain('testMatch: /cross-browser-smoke\\.spec\\.ts/');
  });

  it("[TASK-024-RED-02] adds a browser-agnostic smoke journey for the cross-browser lane", () => {
    const specPath = resolve(
      process.cwd(),
      "src",
      "tests",
      "e2e",
      "cross-browser-smoke.spec.ts",
    );

    expect(existsSync(specPath)).toBe(true);

    const spec = readFileSync(specPath, "utf8");
    expect(spec).toContain("TASK-024");
    expect(spec).toContain('await page.goto("/",');
    expect(spec).toContain("view live demo");
  });
});
