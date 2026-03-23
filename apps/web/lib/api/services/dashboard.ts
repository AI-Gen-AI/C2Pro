import { getCoherenceDashboardApiCoherenceDashboardProjectIdGet } from "@/lib/api/generated/coherence-dashboard/coherence-dashboard";
import { listProjectsApiV1ProjectsGet } from "@/lib/api/generated/projects/projects";
import type { DashboardSummary, ProjectListItem } from "@/lib/api/contracts";

export async function listProjects(): Promise<ProjectListItem[]> {
  const response = await listProjectsApiV1ProjectsGet();
  return response.items ?? [];
}

export async function getDashboardSummary(
  projectId: string,
): Promise<DashboardSummary> {
  const summary =
    await getCoherenceDashboardApiCoherenceDashboardProjectIdGet(projectId);

  return {
    project_id: String(summary.project_id ?? projectId),
    tenant_id: String(summary.tenant_id ?? ""),
    coherence_score: Number(
      summary.coherence_score ?? summary.global_score ?? 0,
    ),
    global_score: Number(summary.global_score ?? summary.coherence_score ?? 0),
    sub_scores: normalizeNumberMap(summary.sub_scores),
    weights_used: normalizeNumberMap(summary.weights_used),
    alert_count: Number(summary.alert_count ?? 0),
    document_count: Number(summary.document_count ?? 0),
    methodology_version: String(summary.methodology_version ?? "unknown"),
    last_updated:
      typeof summary.last_updated === "string" ? summary.last_updated : null,
  };
}

function normalizeNumberMap(value: unknown): Record<string, number> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(value).map(([key, entry]) => [key, Number(entry ?? 0)]),
  );
}
