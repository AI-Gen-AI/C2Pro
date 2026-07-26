/**
 * Test Suite ID: TS-FRT-COV-002 / TASK-FRT-132..135
 * API utilities and helpers
 * Centralized API functions for data fetching
 */

import type { Alert } from "@/types/project";
import type { AlertResponse, DocumentListResponse } from "@/types/backend";
import type { Highlight, Rectangle } from "@/types/highlight";
import { env } from "@/config/env";
import type {
  ApprovalResponse,
  ApprovalStatus,
  DocumentType,
} from "@/lib/api/generated/models";
import { reviewResourceApiV1ApprovalsResourceTypeResourceIdPatch } from "@/lib/api/generated/approvals/approvals";
import { createHighlight, getHighlightColor } from "@/types/highlight";
import { apiClient, handleAuthErrorStatus } from "./client";

/**
 * Processed entity type for document analysis
 */
export interface ProcessedEntity {
  id: string;
  type: "stakeholder" | "wbs" | "bom" | "clause";
  text: string;
  page: number;
  confidence: number;
  metadata?: Record<string, unknown>;
}

interface EvidenceLocation {
  bbox: [number, number, number, number];
  normalized?: boolean;
  page_number?: number;
}

export interface EvidenceHistoryEvent {
  id: string;
  title: string;
  detail: string;
  occurredAt: string;
  sourceType?: string | null;
  sourceId?: string | null;
}

export interface RelationshipExplanationCitation {
  clauseId: string;
  clauseCode: string;
  label: string;
  page: number | null;
  reason: string;
}

export interface DocumentRelationshipExplanation {
  summary: string;
  strongestCluster: string;
  reviewPriority: string;
  latestSignal: string;
  citations: RelationshipExplanationCitation[];
}

export interface AlertRuleConfig {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  threshold: number;
  severity: "Critical" | "High" | "Medium";
}

export interface AlertSubscriptionConfig {
  emailEnabled: boolean;
  emailAddress: string;
  slackEnabled: boolean;
  slackChannel: string;
}

export interface AlertWorkspaceSettings {
  rules: AlertRuleConfig[];
  subscriptions: AlertSubscriptionConfig | null;
}

export interface BulkResolveAlertsRequest {
  alertIds: string[];
  resolution: string;
  rootCause?: string | null;
}

export interface BulkResolveAlertsResponse {
  processedCount: number;
  status: string;
  alertIds: string[];
}

/**
 * Fetch alerts for a specific document
 */
export async function getDocumentAlerts(documentId: string): Promise<Alert[]> {
  const response = await apiClient.get<{
    items: AlertResponse[];
    total: number;
  }>("/alerts/tenant", {
    params: { document_id: documentId },
  });
  return response.data.items;
}

/**
 * Create PDF highlights from alert data
 */
export function createHighlightsFromAlerts(alerts: Alert[]): Highlight[] {
  return alerts.flatMap((alert) => {
    const evidence = extractEvidenceLocation(alert);
    if (!evidence) return [];

    const rect: Rectangle = {
      top: evidence.bbox[1],
      left: evidence.bbox[0],
      width: evidence.bbox[2],
      height: evidence.bbox[3],
      normalized: evidence.normalized,
    };

    return [
      createHighlight(
        alert.id,
        evidence.page_number,
        [rect],
        severityToColor(alert.severity),
        alert.title,
      ),
    ];
  });
}

/**
 * Fetch entities extracted from a document
 */
export async function getDocumentEntities(
  documentId: string,
): Promise<ProcessedEntity[]> {
  const response = await apiClient.get<ProcessedEntity[]>(
    `/documents/${documentId}/entities`,
  );
  return response.data;
}

/**
 * Create PDF highlights from extracted entities
 * Maps extracted entities with evidence locations to PDF highlights
 */
export function createHighlightsFromEntities(
  entities: ProcessedEntity[],
): Highlight[] {
  return entities.flatMap((entity) => {
    const evidence = parseEvidenceLocation(entity.metadata?.evidence_location);
    if (!evidence) return [];

    const rect: Rectangle = {
      left: evidence.bbox[0],
      top: evidence.bbox[1],
      width: evidence.bbox[2],
      height: evidence.bbox[3],
      normalized: evidence.normalized,
    };

    return [
      createHighlight(
        entity.id,
        evidence.page_number || entity.page,
        [rect],
        getHighlightColor(entity.confidence * 100),
        entity.text,
      ),
    ];
  });
}

/**
 * Paginated document list response from API
 */
interface PaginatedDocumentListResponse {
  items: DocumentListResponse[];
  total_count: number;
  skip: number;
  limit: number;
}

/**
 * Fetch documents for a specific project
 */
export async function getProjectDocuments(
  projectId: string,
): Promise<DocumentListResponse[]> {
  const response = await apiClient.get<PaginatedDocumentListResponse>(
    `/projects/${projectId}/documents`,
  );
  // API returns paginated response with items array
  return response.data.items;
}

/**
 * Upload a document to a project
 * Note: File uploads go directly to backend to avoid Next.js proxy
 * which sets Content-Type: application/json and breaks multipart uploads
 */
export async function uploadDocument(
  projectId: string,
  file: File,
  documentType: DocumentType = "contract",
  authOverride?: {
    token?: string | null;
    tenantId?: string | null;
  },
): Promise<{ id: string; task_id: string }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", documentType);

  // Import auth store to get token - file uploads go directly to backend
  const { useAuthStore } = await import("@/stores/auth");
  const storeAuth = useAuthStore.getState();
  const token = authOverride?.token ?? storeAuth.token;
  const tenantId = authOverride?.tenantId ?? storeAuth.tenantId;

  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (tenantId) {
    headers["X-Tenant-ID"] = tenantId;
  }

  const response = await fetch(
    `${env.API_BASE_URL}/projects/${projectId}/documents`,
    {
      method: "POST",
      headers,
      body: formData,
    },
  );

  if (!response.ok) {
    handleAuthErrorStatus(response.status);
    const errorData = await response
      .json()
      .catch(() => ({ detail: "Upload failed" }));
    throw new Error(errorData.detail || `Upload failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Get document download URL
 */
export function getDocumentDownloadUrl(documentId: string): string {
  return `${env.API_BASE_URL}/documents/${documentId}/download`;
}

/**
 * Delete a document by ID
 */
export async function deleteDocument(documentId: string): Promise<void> {
  await apiClient.delete(`/documents/${documentId}`);
}

/**
 * Review an alert (Approve/Reject)
 */
export async function reviewAlert(
  alertId: string,
  decision: "approve" | "reject",
  comment: string = "",
): Promise<AlertResponse> {
  const response = await apiClient.post<AlertResponse>(
    `/alerts/${alertId}/review`,
    {
      decision,
      comment,
    },
  );
  return response.data;
}

export async function reviewApprovalResource(
  resourceType: string,
  resourceId: string,
  status: ApprovalStatus,
  options?: {
    correctionData?: Record<string, unknown>;
    feedbackComment?: string;
  },
): Promise<ApprovalResponse> {
  return reviewResourceApiV1ApprovalsResourceTypeResourceIdPatch(
    resourceType,
    resourceId,
    {
      status,
      correction_data: options?.correctionData,
      feedback_comment: options?.feedbackComment ?? null,
    },
  );
}

/**
 * Resolve an alert
 */
export async function resolveAlert(
  alertId: string,
  resolution: string,
  resolvedBy: string,
  rootCause?: string,
): Promise<AlertResponse> {
  const response = await apiClient.post<AlertResponse>(
    `/alerts/${alertId}/resolve`,
    {
      resolution,
      resolved_by: resolvedBy,
      root_cause: rootCause,
    },
  );
  return response.data;
}

export async function getDocumentHistory(
  documentId: string,
): Promise<EvidenceHistoryEvent[]> {
  type DocumentHistoryApiResponse = {
    document_id: string;
    items: {
      id: string;
      title: string;
      detail: string;
      occurred_at: string;
      source_type?: string | null;
      source_id?: string | null;
    }[];
  };

  const response = await apiClient.get<DocumentHistoryApiResponse>(
    `/documents/${documentId}/history`,
  );

  return response.data.items.map((item: DocumentHistoryApiResponse["items"][number]) => ({
    id: item.id,
    title: item.title,
    detail: item.detail,
    occurredAt: item.occurred_at,
    sourceType: item.source_type ?? null,
    sourceId: item.source_id ?? null,
  }));
}

export async function getDocumentRelationshipExplanation(
  documentId: string,
): Promise<DocumentRelationshipExplanation> {
  type DocumentRelationshipExplanationApiResponse = {
    document_id: string;
    summary: string;
    strongest_cluster: string;
    review_priority: string;
    latest_signal: string;
    citations: {
      clause_id: string;
      clause_code: string;
      label: string;
      page?: number | null;
      reason: string;
    }[];
  };
  type DocumentRelationshipExplanationCitationApi =
    DocumentRelationshipExplanationApiResponse["citations"][number];

  const response = await apiClient.get<DocumentRelationshipExplanationApiResponse>(
    `/documents/${documentId}/relationship-explanation`,
  );

  return {
    summary: response.data.summary,
    strongestCluster: response.data.strongest_cluster,
    reviewPriority: response.data.review_priority,
    latestSignal: response.data.latest_signal,
    citations: response.data.citations.map((citation: DocumentRelationshipExplanationCitationApi) => ({
      clauseId: citation.clause_id,
      clauseCode: citation.clause_code,
      label: citation.label,
      page: citation.page ?? null,
      reason: citation.reason,
    })),
  };
}

export async function getAlertWorkspaceSettings(): Promise<AlertWorkspaceSettings | null> {
  type AlertWorkspaceSettingsApiResponse = {
    rules: AlertRuleConfig[];
    subscriptions: AlertSubscriptionConfig | null;
  };

  const response = await apiClient.get<AlertWorkspaceSettingsApiResponse>(
    "/alerts/workspace-settings",
  );

  return {
    rules: response.data.rules ?? [],
    subscriptions: response.data.subscriptions ?? null,
  };
}

export async function saveAlertWorkspaceSettings(
  payload: AlertWorkspaceSettings,
): Promise<AlertWorkspaceSettings> {
  const response = await apiClient.put<AlertWorkspaceSettings>(
    "/alerts/workspace-settings",
    payload,
  );

  return {
    rules: response.data.rules ?? [],
    subscriptions: response.data.subscriptions ?? null,
  };
}

export async function bulkResolveAlerts(
  payload: BulkResolveAlertsRequest,
): Promise<BulkResolveAlertsResponse> {
  type BulkResolveAlertsApiResponse = {
    processed_count: number;
    status: string;
    alert_ids: string[];
  };

  const response = await apiClient.post<BulkResolveAlertsApiResponse>(
    "/alerts/bulk-resolve",
    {
      alert_ids: payload.alertIds,
      resolution: payload.resolution,
      root_cause: payload.rootCause ?? null,
    },
  );

  return {
    processedCount: response.data.processed_count,
    status: response.data.status,
    alertIds: response.data.alert_ids,
  };
}

/**
 * Update a stakeholder's details
 */
export async function updateStakeholder(
  stakeholderId: string,
  data: {
    name?: string;
    role?: string;
    company?: string;
    email?: string;
    power_score?: number;
    interest_score?: number;
    stakeholder_metadata?: Record<string, unknown>;
  },
): Promise<unknown> {
  const response = await apiClient.patch<unknown>(
    `/stakeholders/${stakeholderId}`,
    data,
  );
  return response.data;
}

/**
 * Update a WBS item
 */
export async function updateWBSItem(
  wbsId: string,
  data: {
    name?: string;
    description?: string;
    planned_start?: string;
    planned_end?: string;
    status?: string;
  },
): Promise<unknown> {
  const response = await apiClient.put<unknown>(`/procurement/wbs/${wbsId}`, data);
  return response.data;
}

/**
 * Update a BOM item
 */
export async function updateBOMItem(
  bomId: string,
  data: {
    item_name?: string;
    quantity?: number;
    unit?: string;
    unit_price?: number;
    status?: string;
  },
): Promise<unknown> {
  const response = await apiClient.put<unknown>(`/procurement/bom/${bomId}`, data);
  return response.data;
}

export function extractEvidenceLocation(alert: Alert): {
  page_number: number;
  bbox: [number, number, number, number];
  normalized?: boolean;
} | null {
  const alertAny = alert as AlertResponse;
  const direct = alertAny.evidence_location;
  const nested = alertAny.evidence_json?.evidence_location;
  const candidate = direct || nested;
  if (!candidate || !Array.isArray(candidate.bbox)) {
    return null;
  }
  const normalized =
    candidate.normalized ??
    candidate.bbox.every((value: number) => value >= 0 && value <= 1);
  return {
    page_number: candidate.page_number,
    bbox: candidate.bbox,
    normalized,
  };
}

export function parseEvidenceLocation(value: unknown): EvidenceLocation | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const candidate = value as {
    bbox?: unknown;
    normalized?: unknown;
    page_number?: unknown;
  };

  if (
    !Array.isArray(candidate.bbox) ||
    candidate.bbox.length !== 4 ||
    !candidate.bbox.every((point): point is number => typeof point === "number")
  ) {
    return null;
  }

  return {
    bbox: [
      candidate.bbox[0],
      candidate.bbox[1],
      candidate.bbox[2],
      candidate.bbox[3],
    ],
    normalized: typeof candidate.normalized === "boolean" ? candidate.normalized : undefined,
    page_number: typeof candidate.page_number === "number" ? candidate.page_number : undefined,
  };
}

export function severityToColor(severity: Alert["severity"] | string | undefined): string {
  const normalized = String(severity).toLowerCase();
  switch (normalized) {
    case "critical":
      return "red";
    case "high":
      return "orange";
    case "medium":
      return "yellow";
    default:
      return "blue";
  }
}

// Re-export API client and auth utilities
export * from "./client";
export * from "./auth";
export * from "./config";
