/**
 * Test Suite ID: TASK-FRT-188
 * Audit Report export composition helpers.
 */
import type { AlertResponse, ReviewItemResponse } from "@/lib/api/generated/models";
import type { CoherenceV2Payload, DashboardSummary } from "@/lib/api/contracts";
import type { DocumentInfo } from "@/types/document";
import type { Project } from "@/types/project";

type ProjectSource = Pick<Project, "id" | "name" | "code" | "status"> & {
  client_name?: string | null;
};

export type ReportAlert = {
  id: string;
  category: string;
  severity: string;
  status: string;
  message: string;
  evidenceReferences: string[];
  createdAt: string;
  reviewedBy?: string | null;
  reviewedAt?: string | null;
};

export type ReportAlertGroups = {
  open: ReportAlert[];
  approved: ReportAlert[];
  rejected: ReportAlert[];
};

export type ReportDocument = {
  id: string;
  name: string;
  type: string;
  uploadedAt: string | null;
  status?: string;
};

export type ReportReviewDecision = {
  id: string;
  type: string;
  status: string;
  reviewer: string;
  reviewedAt: string;
  summary: string | null;
};

export type AuditReportPayload = {
  generatedAt: string;
  project: {
    id: string;
    name: string;
    code?: string | null;
    status?: string;
    clientName?: string | null;
  };
  score: {
    value: number | null;
    label: string;
    scoreVersion?: string | null;
    reason?: string | null;
  };
  categoriesV2: CoherenceV2Payload | null;
  alertGroups: ReportAlertGroups;
  documents: ReportDocument[];
  reviewDecisions: ReportReviewDecision[];
  reviewDecisionSource: "project_scoped" | "not_project_scoped";
};

type ComposeAuditReportInput = {
  project: ProjectSource;
  dashboard: DashboardSummary | null;
  alerts: AlertResponse[];
  documents: DocumentInfo[];
  reviewItems?: ReviewItemResponse[];
  reviewItemsProjectScoped?: boolean;
  generatedAt: string;
};

export function composeAuditReport({
  project,
  dashboard,
  alerts,
  documents,
  reviewItems,
  reviewItemsProjectScoped = false,
  generatedAt,
}: ComposeAuditReportInput): AuditReportPayload {
  const score = dashboard?.coherence_score ?? dashboard?.global_score ?? null;

  return {
    generatedAt,
    project: {
      id: project.id,
      name: project.name,
      code: project.code ?? null,
      status: project.status,
      clientName: project.client_name ?? null,
    },
    score: {
      value: score,
      label: score === null ? "Pending evidence" : String(score),
      scoreVersion: dashboard?.score_version ?? null,
      reason: dashboard?.score_reason ?? null,
    },
    categoriesV2: dashboard?.categories_v2 ?? null,
    alertGroups: groupReportAlerts(alerts),
    documents: documents.map((document) => ({
      id: document.id,
      name: document.name,
      type: document.type,
      uploadedAt: document.uploadedAt?.toISOString() ?? null,
      status: document.status,
    })),
    reviewDecisions: reviewItemsProjectScoped
      ? (reviewItems ?? []).flatMap(toReviewDecision)
      : [],
    reviewDecisionSource: reviewItemsProjectScoped
      ? "project_scoped"
      : "not_project_scoped",
  };
}

export function groupReportAlerts(alerts: AlertResponse[]): ReportAlertGroups {
  const groups: ReportAlertGroups = {
    open: [],
    approved: [],
    rejected: [],
  };

  for (const alert of alerts) {
    const item = toReportAlert(alert);
    const status = alert.status.toLowerCase();
    if (["approved", "resolved"].includes(status)) {
      groups.approved.push(item);
    } else if (["rejected", "dismissed"].includes(status)) {
      groups.rejected.push(item);
    } else {
      groups.open.push(item);
    }
  }

  return groups;
}

export function downloadAuditReportJson(payload: AuditReportPayload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `audit-report-${payload.project.id}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function toReportAlert(alert: AlertResponse): ReportAlert {
  return {
    id: alert.id,
    category: alert.category,
    severity: alert.severity,
    status: alert.status,
    message: alert.message,
    evidenceReferences: buildEvidenceReferences(alert.affected_entities),
    createdAt: alert.created_at,
    reviewedBy: alert.reviewed_by,
    reviewedAt: alert.reviewed_at,
  };
}

function buildEvidenceReferences(
  affectedEntities: AlertResponse["affected_entities"],
): string[] {
  const references: string[] = [];
  const documentName = firstString(affectedEntities, [
    "document_name",
    "documentName",
    "filename",
    "file_name",
    "source_document",
  ]);
  const page = firstValue(affectedEntities, ["page", "page_number", "pageNumber"]);
  const clause = firstString(affectedEntities, [
    "clause",
    "clause_id",
    "clauseId",
    "clause_reference",
  ]);

  if (documentName) references.push(documentName);
  if (page !== null) references.push(`Page ${page}`);
  if (clause) references.push(`Clause ${clause}`);

  return references;
}

function toReviewDecision(item: ReviewItemResponse): ReportReviewDecision[] {
  if (!item.approved_by || !item.approved_at) {
    return [];
  }

  return [
    {
      id: item.item_id,
      type: item.item_type,
      status: item.current_status,
      reviewer: item.approved_by,
      reviewedAt: item.approved_at,
      summary: firstString(item.item_data, ["summary", "message", "description", "title"]),
    },
  ];
}

function firstString(
  value: Record<string, unknown> | null | undefined,
  keys: string[],
): string | null {
  for (const key of keys) {
    const entry = value?.[key];
    if (typeof entry === "string" && entry.trim().length > 0) {
      return entry.trim();
    }
  }

  return null;
}

function firstValue(
  value: Record<string, unknown> | null | undefined,
  keys: string[],
): string | number | null {
  for (const key of keys) {
    const entry = value?.[key];
    if (typeof entry === "string" && entry.trim().length > 0) {
      return entry.trim();
    }
    if (typeof entry === "number") {
      return entry;
    }
  }

  return null;
}
