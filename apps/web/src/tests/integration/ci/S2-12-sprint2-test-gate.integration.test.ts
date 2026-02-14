/**
 * Test Suite ID: S2-12
 * Roadmap Reference: S2-12 Sprint 2 test completion gate (35 unit + 12 integration + 4 E2E)
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { resolve, extname, basename } from "node:path";

type Layer = "unit" | "integration" | "e2e";

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

function classifyLayer(path: string): Layer | null {
  if (path.includes("\\src\\tests\\e2e\\") || path.includes("/src/tests/e2e/")) {
    return "e2e";
  }
  if (
    path.includes("\\src\\tests\\integration\\") ||
    path.includes("/src/tests/integration/")
  ) {
    return "integration";
  }
  if (path.includes("\\src\\") || path.includes("/src/")) {
    return "unit";
  }
  return null;
}

describe("S2-12 RED - Sprint 2 test gate", () => {
  it("[S2-12-RED-01] has at least 35 S2-12 unit tests", () => {
    const webRoot = resolve(process.cwd());
    const allFiles = walkFiles(resolve(webRoot, "src"));
    const s2Unit = allFiles.filter((file) => {
      if (!isTestFile(file) || extname(file) === ".map") return false;
      if (classifyLayer(file) !== "unit") return false;
      const content = readFileSync(file, "utf-8");
      return content.includes("S2-12");
    });

    expect(s2Unit.length).toBeGreaterThanOrEqual(35);
  });

  it("[S2-12-RED-02] has at least 12 S2-12 integration tests", () => {
    const webRoot = resolve(process.cwd());
    const integrationRoot = resolve(webRoot, "src", "tests", "integration");
    const allFiles = walkFiles(integrationRoot);
    const s2Integration = allFiles.filter((file) => {
      if (!isTestFile(file) || extname(file) === ".map") return false;
      const content = readFileSync(file, "utf-8");
      return content.includes("S2-12");
    });

    expect(s2Integration.length).toBeGreaterThanOrEqual(12);
  });

  it("[S2-12-RED-03] has at least 4 S2-12 E2E tests", () => {
    const webRoot = resolve(process.cwd());
    const e2eRoot = resolve(webRoot, "src", "tests", "e2e");

    const e2eFiles = existsSync(e2eRoot)
      ? walkFiles(e2eRoot).filter((file) => isTestFile(file))
      : [];

    const s2E2E = e2eFiles.filter((file) =>
      readFileSync(file, "utf-8").includes("S2-12"),
    );

    expect(s2E2E.length).toBeGreaterThanOrEqual(4);
  });

  it("[S2-12-RED-04] defines sprint-2 acceptance E2E flow for project to coherence pipeline", () => {
    const e2eFlow = resolve(
      process.cwd(),
      "src",
      "tests",
      "e2e",
      "S2-12-project-coherence-flow.spec.ts",
    );

    expect(existsSync(e2eFlow)).toBe(true);

    const content = readFileSync(e2eFlow, "utf-8");
    expect(content).toContain("S2-12");
    expect(content).toContain("Project");
    expect(content).toContain("Coherence");
    expect(content).toContain("Upload");
    expect(content).toContain("SSE");
  });
});
