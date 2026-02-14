import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("S1-15 document layer rules ADR", () => {
  it("documents the server vs client component data access rules", () => {
    const adrPath = resolve(
      process.cwd(),
      "..",
      "..",
      "docs",
      "architecture",
      "decisions",
      "004-frontend-layer-rules.md",
    );
    const adr = readFileSync(adrPath, "utf-8");

    expect(adr).toContain("ADR-002");
    expect(adr).toContain("Server Components");
    expect(adr).toContain("Client Components");
    expect(adr).toContain("MAY fetch data directly via `lib/api/generated`");
    expect(adr).toContain("MUST use Orval-generated TanStack Query hooks");
    expect(adr).toContain("MUST NOT use hooks");
    expect(adr).toContain(
      "MUST NOT import from `lib/api/generated` directly",
    );
  });
});
