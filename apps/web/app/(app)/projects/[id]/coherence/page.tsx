import type { DashboardSummary } from "@/lib/api/contracts";
import { CoherenceClient } from "@/components/coherence/CoherenceClient";
import { getDashboardSummary } from "@/lib/api/services/dashboard";
import { BarChart3 } from "lucide-react";

export default async function ProjectCoherencePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams?: Promise<{ cohV1Scenario?: string }>;
}) {
  const { id } = await params;
  const scenario = (await searchParams)?.cohV1Scenario;

  let summary: DashboardSummary | null = null;
  let loadError: string | null = null;

  try {
    summary =
      process.env.NODE_ENV !== "production" && scenario
        ? buildCoherenceV1Scenario(id, scenario)
        : await getDashboardSummary(id, { server: true });
  } catch (error) {
    loadError =
      error instanceof Error
        ? error.message
        : "Could not load coherence data right now.";
  }

  return (
    <div className="space-y-5">
      {loadError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {loadError}. Verify backend API is running at{" "}
          <code>http://localhost:8000</code>.
        </div>
      ) : null}

      {!loadError && !summary ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed bg-card py-16 text-center">
          <BarChart3 className="mb-3 h-10 w-10 text-muted-foreground/50" />
          <h3 className="text-sm font-medium text-foreground">
            No coherence data yet
          </h3>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">
            Upload and analyze documents for this project to generate coherence
            scores.
          </p>
        </div>
      ) : null}

      {summary ? <CoherenceClient summary={summary} /> : null}
    </div>
  );
}

function buildCoherenceV1Scenario(projectId: string, scenario: string): DashboardSummary {
  if (scenario === "contract-only") {
    return {
      project_id: projectId,
      tenant_id: "tenant-demo",
      coherence_score: null,
      global_score: null,
      sub_scores: {},
      weights_used: {},
      alert_count: 1,
      document_count: 1,
      methodology_version: "v1",
      score_version: "v1_exponential_decay",
      score_reason: "insufficient_evidence",
      score_missing_dimensions: ["schedule", "budget"],
      last_updated: "2026-05-01T00:00:00Z",
    };
  }

  return {
    project_id: projectId,
    tenant_id: "tenant-demo",
    coherence_score: 82,
    global_score: 82,
    sub_scores: {
      SCOPE: 84,
      BUDGET: 78,
      QUALITY: 86,
      TECHNICAL: 80,
      LEGAL: 88,
      TIME: 76,
    },
    weights_used: {
      SCOPE: 0.17,
      BUDGET: 0.17,
      QUALITY: 0.16,
      TECHNICAL: 0.16,
      LEGAL: 0.17,
      TIME: 0.17,
    },
    alert_count: 3,
    document_count: 3,
    methodology_version: "v1",
    score_version: "v1_exponential_decay",
    score_reason: null,
    score_missing_dimensions: [],
    last_updated: "2026-05-01T00:00:00Z",
  };
}
