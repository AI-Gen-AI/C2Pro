import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function readRepoFile(...segments: string[]) {
  return readFileSync(resolve(process.cwd(), "..", "..", ...segments), "utf-8");
}

describe("API generation drift safeguards", () => {
  it("isolates generated Orval mocks under a dedicated __mocks__ directory", () => {
    const config = readRepoFile("apps", "web", "orval.config.ts");

    expect(config).toContain('output: "./lib/api/generated/__mocks__"');
    expect(config).toContain("useInfinite: false");
  });

  it("keeps generated mock code out of production webpack bundles", () => {
    const nextConfig = readRepoFile("apps", "web", "next.config.mjs");

    expect(nextConfig).toContain("IgnorePlugin");
    expect(nextConfig).toContain("/__mocks__/");
  });

  it("fails CI when generated client or checked-in OpenAPI schema drift", () => {
    const pkg = readRepoFile("apps", "web", "package.json");

    expect(pkg).toContain(
      '"generate:api:check": "orval && pnpm exec prettier --write lib/api/generated schema/api.json && git diff --exit-code -- lib/api/generated schema/api.json"',
    );
  });

  it("keeps drift gates wired for backend and frontend API changes", () => {
    // Since TASK-DEV-003 the drift topology is split: openapi-drift.yml gates
    // backend spec drift on apps/api changes, and ci.yml's frontend lane runs
    // the Orval generation drift check (schema/api.json lives in apps/web).
    const openapiDrift = readRepoFile(".github", "workflows", "openapi-drift.yml");
    const ci = readRepoFile(".github", "workflows", "ci.yml");

    expect(openapiDrift).toContain('- "apps/api/src/**"');
    expect(ci).toContain("pnpm generate:api:check");
  });
});
