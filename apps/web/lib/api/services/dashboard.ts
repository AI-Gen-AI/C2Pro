import type { DashboardSummary, ProjectListItem } from "@/lib/api/contracts";
import { fetchApiJson } from "@/lib/api/services/http";

type ListProjectsResponse = {
  items?: ProjectListItem[];
};

type DashboardSummaryResponse = Partial<DashboardSummary> & {
  global_score?: number | string | null;
  coherence_score?: number | string | null;
  sub_scores?: Record<string, unknown> | null;
  weights_used?: Record<string, unknown> | null;
  alert_count?: number | string | null;
  document_count?: number | string | null;
};

export async function listProjects(options?: {
  server?: boolean;
}): Promise<ProjectListItem[]> {
  const response = await fetchApiJson<ListProjectsResponse>("projects", options);
  return response.items ?? [];
}

export async function getDashboardSummary(
  projectId: string,
  options?: {
    server?: boolean;
  },
): Promise<DashboardSummary> {
  const summary = await fetchApiJson<DashboardSummaryResponse>(
    `dashboard/${projectId}`,
    {
      ...options,
      scope: "coherence",
    },
  );

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
