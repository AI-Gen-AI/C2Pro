import { describe, expect, it } from "vitest";
import type { HealthVector } from "@/types/health";
import { mockProjectHealthVector, projectHealthHandler } from "./project-health";

describe("project health MSW contract", () => {
  it("exposes the project-scoped health endpoint", () => {
    expect(String(projectHealthHandler.info.path)).toContain(
      "/api/v1/projects/:projectId/health",
    );
  });

  it("returns a typed honest health vector mock", () => {
    const vector: HealthVector = mockProjectHealthVector("project-1", "tenant-1");

    expect(vector.project_id).toBe("project-1");
    expect(vector.tenant_id).toBe("tenant-1");
    expect(vector.composite_score).toBeNull();
    expect(vector.composite_band).toBe("unknown");
    expect(vector.dimensions.every((dimension) => dimension.score === null)).toBe(
      true,
    );
  });
});
