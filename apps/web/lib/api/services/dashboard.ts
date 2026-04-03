import type {
  DashboardSummary,
  ProjectListItem,
  ProjectQuickViewSummary,
} from "@/lib/api/contracts";
import { fetchApiJson } from "@/lib/api/services/http";

type ListProjectsResponse = {
  items?: Array<Record<string, unknown>>;
};

type DashboardSummaryResponse = Partial<DashboardSummary> & {
  global_score?: number | string | null;
  coherence_score?: number | string | null;
  sub_scores?: Record<string, unknown> | null;
  weights_used?: Record<string, unknown> | null;
  alert_count?: number | string | null;
  document_count?: number | string | null;
};

type ProjectQuickViewSummaryResponse = Partial<ProjectQuickViewSummary> & {
  coherence_score?: number | string | null;
  open_alert_count?: number | string | null;
  critical_alert_count?: number | string | null;
  top_alerts?: Array<{
    id?: string | null;
    title?: string | null;
    severity?: string | null;
    status?: string | null;
    created_at?: string | null;
  }> | null;
};

export async function listProjects(options?: {
  server?: boolean;
}): Promise<ProjectListItem[]> {
  const response = await fetchApiJson<ListProjectsResponse>("projects", options);
  return Array.isArray(response.items)
    ? response.items.map((item) => ({
        id: String(item.id ?? ""),
        tenant_id: String(item.tenant_id ?? ""),
        name: String(item.name ?? ""),
        code: item.code ? String(item.code) : null,
        description: item.description ? String(item.description) : null,
        project_type: item.project_type ? String(item.project_type) : undefined,
        status: item.status ? String(item.status) : undefined,
        coherence_score:
          item.coherence_score == null ? null : Number(item.coherence_score),
        location: item.location ? String(item.location) : null,
        client_name: item.client_name ? String(item.client_name) : null,
        budget_planned:
          item.budget_planned == null ? null : Number(item.budget_planned),
        estimated_budget:
          item.estimated_budget == null ? null : Number(item.estimated_budget),
        currency: item.currency ? String(item.currency) : undefined,
        version: item.version == null ? undefined : Number(item.version),
        alert_count: item.alert_count == null ? null : Number(item.alert_count),
        critical_alert_count:
          item.critical_alert_count == null
            ? null
            : Number(item.critical_alert_count),
        coherence_score_delta:
          item.coherence_score_delta == null
            ? null
            : Number(item.coherence_score_delta),
        alert_count_delta:
          item.alert_count_delta == null
            ? null
            : Number(item.alert_count_delta),
        updated_at: item.updated_at ? String(item.updated_at) : null,
      }))
    : [];
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

export async function getProjectQuickViewSummary(
  projectId: string,
  options?: {
    server?: boolean;
  },
): Promise<ProjectQuickViewSummary> {
  const summary = await fetchApiJson<ProjectQuickViewSummaryResponse>(
    `projects/${projectId}/summary`,
    options,
  );

  return {
    project_id: String(summary.project_id ?? projectId),
    tenant_id: String(summary.tenant_id ?? ""),
    name: String(summary.name ?? ""),
    code: summary.code ? String(summary.code) : null,
    description: summary.description ? String(summary.description) : null,
    project_type: String(summary.project_type ?? "construction"),
    status: String(summary.status ?? "draft"),
    coherence_score: Number(summary.coherence_score ?? 0),
    client_name: summary.client_name ? String(summary.client_name) : null,
    open_alert_count: Number(summary.open_alert_count ?? 0),
    critical_alert_count: Number(summary.critical_alert_count ?? 0),
    top_alerts: Array.isArray(summary.top_alerts)
      ? summary.top_alerts.map((alert, index) => ({
          id: String(alert.id ?? `alert-${index}`),
          title: String(alert.title ?? "Untitled alert"),
          severity: String(alert.severity ?? "unknown"),
          status: String(alert.status ?? "unknown"),
          created_at: String(alert.created_at ?? ""),
        }))
      : [],
    updated_at:
      typeof summary.updated_at === "string" ? summary.updated_at : null,
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
