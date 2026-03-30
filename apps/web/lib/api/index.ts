/**
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
  metadata?: Record<string, any>;
}

/**
 * Fetch alerts for a specific document
 */
export async function getDocumentAlerts(documentId: string): Promise<Alert[]> {
  const response = await apiClient.get<{
    items: AlertResponse[];
    total: number;
  }>("/alerts", {
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
  _pageHeight?: number,
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
    const evidence = entity.metadata?.evidence_location;
    if (!evidence || !Array.isArray(evidence.bbox)) return [];

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
  documentType:
    | "CONTRACT"
    | "SCHEDULE"
    | "BOM"
    | "SPECIFICATION"
    | "DRAWING"
    | "OTHER" = "CONTRACT",
): Promise<{ id: string; task_id: string }> {
  const formData = new FormData();
  formData.append("file", file);
  // Backend enum expects lowercase values (contract, schedule, etc.)
  formData.append("document_type", documentType.toLowerCase());

  // Import auth store to get token - file uploads go directly to backend
  const { useAuthStore } = await import("@/stores/auth");
  const { token, tenantId } = useAuthStore.getState();

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
    stakeholder_metadata?: Record<string, any>;
  },
): Promise<any> {
  const response = await apiClient.patch(
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
): Promise<any> {
  const response = await apiClient.put(`/procurement/wbs/${wbsId}`, data);
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
): Promise<any> {
  const response = await apiClient.put(`/procurement/bom/${bomId}`, data);
  return response.data;
}

function extractEvidenceLocation(alert: Alert): {
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

function severityToColor(severity: Alert["severity"]): string {
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
