import { http, HttpResponse } from "@/mocks/msw";
import type { HealthDimension, HealthVector } from "@/types/health";

const HEALTH_DIMENSIONS: HealthDimension[] = [
  "contract",
  "risk",
  "documentation",
  "governance",
];

export function mockProjectHealthVector(
  projectId: string,
  tenantId = "demo-tenant",
): HealthVector {
  return {
    project_id: projectId,
    tenant_id: tenantId,
    dimensions: HEALTH_DIMENSIONS.map((dimension) => ({
      dimension,
      score: null,
      band: "unknown",
      confidence: 0,
      evidence: [],
      trend: "unknown",
      missing_data: ["no health snapshot available"],
      null_reason: "insufficient_evidence",
    })),
    composite_score: null,
    composite_band: "unknown",
    composite_trend: "unknown",
    computed_at: new Date(0).toISOString(),
  };
}

export const projectHealthHandler = http.get(
  "/api/v1/projects/:projectId/health",
  ({ params }) =>
    HttpResponse.json(mockProjectHealthVector(String(params.projectId))),
);
