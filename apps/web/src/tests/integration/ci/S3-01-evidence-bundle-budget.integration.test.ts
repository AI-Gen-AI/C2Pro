/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("S3-01 RED - evidence bundle budget", () => {
  it("[S3-01-RED-PERF-01] keeps evidence route bundle within 120KB", () => {
    const manifestPath = resolve(
      process.cwd(),
      ".next",
      "build-manifest.json",
    );
    expect(existsSync(manifestPath)).toBe(true);

    const manifest = JSON.parse(readFileSync(manifestPath, "utf-8")) as {
      pages?: Record<string, string[]>;
    };
    const evidenceRoute = "/dashboard/projects/[id]/evidence";
    const evidenceChunks = manifest.pages?.[evidenceRoute] ?? [];

    const totalBytes = evidenceChunks.reduce((sum, chunkPath) => {
      const filePath = resolve(process.cwd(), ".next", chunkPath.replace(/^\//, ""));
      if (!existsSync(filePath)) return sum;
      return sum + readFileSync(filePath).byteLength;
    }, 0);

    expect(totalBytes).toBeLessThanOrEqual(120 * 1024);
  });
});
