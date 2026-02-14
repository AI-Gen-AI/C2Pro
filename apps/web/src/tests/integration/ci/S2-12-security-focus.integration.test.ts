/**
 * Test Suite ID: S2-12
 * Security Focus: Prevent test-quality bypass in Sprint 2 gate artifacts
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { resolve, basename } from "node:path";

function walkFiles(dir: string): string[] {
  const entries = readdirSync(dir);
  const files: string[] = [];

  for (const entry of entries) {
    const fullPath = resolve(dir, entry);
    const stats = statSync(fullPath);
    if (stats.isDirectory()) {
      files.push(...walkFiles(fullPath));
      continue;
    }
    files.push(fullPath);
  }

  return files;
}

function isTestFile(path: string): boolean {
  const name = basename(path);
  return (
    name.endsWith(".test.ts") ||
    name.endsWith(".test.tsx") ||
    name.endsWith(".spec.ts") ||
    name.endsWith(".spec.tsx")
  );
}

function getS212Tests(): Array<{ path: string; content: string }> {
  const webRoot = resolve(process.cwd(), "src");
  const files = walkFiles(webRoot).filter((file) => isTestFile(file));

  return files
    .map((path) => ({ path, content: readFileSync(path, "utf-8") }))
    .filter(
      (entry) =>
        !entry.path.endsWith("S2-12-security-focus.integration.test.ts"),
    )
    .filter((entry) => entry.content.includes("S2-12"));
}

describe("S2-12 RED - security quality guard", () => {
  it("[S2-12-SEC-RED-01] forbids hard-skipped S2-12 tests", () => {
    const offenders = getS212Tests().filter(({ content }) =>
      content.includes("test.skip(true"),
    );

    expect(offenders).toHaveLength(0);
  });

  it("[S2-12-SEC-RED-02] forbids tautological placeholder assertions", () => {
    const offenders = getS212Tests().filter(({ content }) =>
      content.includes('expect("S2-12").toContain("S2-12")'),
    );

    expect(offenders).toHaveLength(0);
  });

  it("[S2-12-SEC-RED-03] requires at least one explicit auth-negative assertion", () => {
    const hasAuthNegativeCoverage = getS212Tests().some(({ content }) => {
      const hasStatusExpectation =
        content.includes("401") || content.includes("403");
      const hasAuthErrorSignals =
        content.includes("UNAUTHORIZED") ||
        content.includes("FORBIDDEN") ||
        content.includes("credentials: \"omit\"");
      return hasStatusExpectation && hasAuthErrorSignals;
    });

    expect(hasAuthNegativeCoverage).toBe(true);
  });
});
