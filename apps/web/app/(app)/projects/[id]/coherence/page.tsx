import type { DashboardSummary } from "@/lib/api/contracts";
import { CoherenceClient } from "@/components/coherence/CoherenceClient";
import { getCoherenceDashboardApiCoherenceDashboardProjectIdGet } from "@/lib/api/generated/coherence-dashboard/coherence-dashboard";
import { BarChart3 } from "lucide-react";

export default async function ProjectCoherencePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let summary: DashboardSummary | null = null;
  let loadError: string | null = null;

  try {
    const response =
      await getCoherenceDashboardApiCoherenceDashboardProjectIdGet(id);
    summary = {
      project_id: String(response.project_id ?? id),
      tenant_id: String(response.tenant_id ?? ""),
      coherence_score: Number(
        response.coherence_score ?? response.global_score ?? 0,
      ),
      global_score: Number(
        response.global_score ?? response.coherence_score ?? 0,
      ),
      sub_scores: normalizeNumberMap(response.sub_scores),
      weights_used: normalizeNumberMap(response.weights_used),
      alert_count: Number(response.alert_count ?? 0),
      document_count: Number(response.document_count ?? 0),
      methodology_version: String(response.methodology_version ?? "unknown"),
      last_updated:
        typeof response.last_updated === "string" ? response.last_updated : null,
    };
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

function normalizeNumberMap(value: unknown): Record<string, number> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(value).map(([key, entry]) => [key, Number(entry ?? 0)]),
  );
}
