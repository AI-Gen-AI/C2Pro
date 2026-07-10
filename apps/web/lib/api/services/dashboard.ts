import type {
  DashboardSummary,
  ProjectListItem,
  ProjectQuickViewSummary,
} from "@/lib/api/contracts";
import { fetchApiJson } from "@/lib/api/services/http";

type ListProjectsResponse = {
  items?: Array<Record<string, unknown>>;
};

type DashboardRequestOptions = {
  server?: boolean;
  headers?: HeadersInit;
};

type DashboardSummaryResponse = Partial<DashboardSummary> & {
  global_score?: number | string | null;
  coherence_score?: number | string | null;
  sub_scores?: Record<string, unknown> | null;
  weights_used?: Record<string, unknown> | null;
  alert_count?: number | string | null;
  document_count?: number | string | null;
  score_version?: string | null;
  score_reason?: string | null;
  score_missing_dimensions?: unknown;
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

export async function listProjects(options?: DashboardRequestOptions): Promise<ProjectListItem[]> {
  const response = await fetchApiJson<ListProjectsResponse>("projects", options);
  return Array.isArray(response.items)
    ? response.items.map((item) => ({
        id: primitiveString(item.id, ""),
        tenant_id: primitiveString(item.tenant_id, ""),
        name: primitiveString(item.name, ""),
        code: nullablePrimitiveString(item.code),
        description: nullablePrimitiveString(item.description),
        project_type: optionalPrimitiveString(item.project_type),
        status: optionalPrimitiveString(item.status),
        coherence_score:
          item.coherence_score == null ? null : Number(item.coherence_score),
        location: nullablePrimitiveString(item.location),
        client_name: nullablePrimitiveString(item.client_name),
        budget_planned:
          item.budget_planned == null ? null : Number(item.budget_planned),
        estimated_budget:
          item.estimated_budget == null ? null : Number(item.estimated_budget),
        currency: optionalPrimitiveString(item.currency),
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
        updated_at: nullablePrimitiveString(item.updated_at),
      }))
    : [];
}

export async function getDashboardSummary(
  projectId: string,
  options?: DashboardRequestOptions,
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
    coherence_score: normalizeNullableNumber(summary.coherence_score ?? summary.global_score),
    global_score: normalizeNullableNumber(summary.global_score ?? summary.coherence_score),
    sub_scores: normalizeNumberMap(summary.sub_scores),
    weights_used: normalizeNumberMap(summary.weights_used),
    alert_count: Number(summary.alert_count ?? 0),
    document_count: Number(summary.document_count ?? 0),
    methodology_version: String(summary.methodology_version ?? "unknown"),
    score_version:
      typeof summary.score_version === "string" ? summary.score_version : null,
    score_reason:
      typeof summary.score_reason === "string" ? summary.score_reason : null,
    score_missing_dimensions: normalizeStringList(summary.score_missing_dimensions),
    last_updated:
      typeof summary.last_updated === "string" ? summary.last_updated : null,
  };
}

export async function getProjectQuickViewSummary(
  projectId: string,
  options?: DashboardRequestOptions,
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

function normalizeNullableNumber(value: number | string | null | undefined): number | null {
  return value == null ? null : Number(value);
}

function primitiveString(value: unknown, fallback: string) {
  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean" ||
    typeof value === "bigint"
  ) {
    return String(value);
  }

  return fallback;
}

function nullablePrimitiveString(value: unknown) {
  return value == null ? null : primitiveString(value, "");
}

function optionalPrimitiveString(value: unknown) {
  return value == null ? undefined : primitiveString(value, "");
}

function normalizeStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string");
}
