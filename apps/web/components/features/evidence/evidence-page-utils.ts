import { env } from "@/config/env";
import type { PdfHighlight } from "@/components/features/evidence/PdfEvidenceViewer";
import type { Alert as ProjectAlert } from "@/types/project";

export type EvidenceTemplate = {
  id: string;
  name: string;
  summary: string;
  reviewFocus: string[];
  tags: string[];
};

export type PendingEvidenceAction =
  | {
      kind: "entity-approve";
      entityId: string;
      label: string;
      confidence: number;
    }
  | {
      kind: "entity-reject";
      entityId: string;
      label: string;
      reason: string;
    }
  | {
      kind: "alert-review";
      alertId: string;
      label: string;
      decision: "approve" | "reject";
    };

export type EvidencePanelTab = "entities" | "alerts" | "search";

export const EVIDENCE_TEMPLATES: EvidenceTemplate[] = [
  {
    id: "claims-review",
    name: "Claims Review",
    summary: "Claims review focus",
    reviewFocus: [
      "Delay-event support",
      "Notice compliance",
      "Commercial exposure",
    ],
    tags: ["claims", "time-impact", "commercial"],
  },
  {
    id: "technical-audit",
    name: "Technical Audit",
    summary: "Technical audit focus",
    reviewFocus: [
      "Specification compliance",
      "Design-change evidence",
      "Quality deviation traceability",
    ],
    tags: ["technical", "quality", "design"],
  },
  {
    id: "executive-brief",
    name: "Executive Brief",
    summary: "Executive brief focus",
    reviewFocus: [
      "Critical findings only",
      "Decision-ready evidence",
      "Alert prioritization",
    ],
    tags: ["executive", "summary", "risk"],
  },
];

export function sanitizeFilename(value: string): string {
  return value
    .trim()
    .replace(/[^a-z0-9_.-]+/gi, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "")
    .toLowerCase();
}

export function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

export function downloadBlob(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function normalizeConfidence(value: number): number {
  if (value <= 1) {
    return Math.round(value * 100);
  }
  return Math.round(value);
}

export function normalizeEntityType(value: string): string {
  if (!value) {
    return "Entity";
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function formatEvidenceTimelineDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toISOString().slice(0, 10);
}

export function mapHighlightColorToSeverity(color: string): PdfHighlight["severity"] {
  switch (color) {
    case "red":
      return "critical";
    case "orange":
      return "high";
    case "yellow":
      return "medium";
    case "green":
    case "blue":
    default:
      return "low";
  }
}

export function mapEntityTypeToApprovalResourceType(
  entityType: string,
): string | null {
  switch (entityType) {
    case "stakeholder":
      return "stakeholders";
    default:
      return null;
  }
}

export function extractAlertEvidenceLocation(alert: ProjectAlert): {
  page_number: number;
  bbox: [number, number, number, number];
  normalized?: boolean;
} | null {
  const evidence = (alert.evidence_json as { evidence_location?: {
    page_number: number;
    bbox: [number, number, number, number];
    normalized?: boolean;
  } } | undefined)?.evidence_location;

  if (!evidence || !Array.isArray(evidence.bbox)) {
    return null;
  }

  const normalized =
    evidence.normalized ??
    evidence.bbox.every((value) => value >= 0 && value <= 1);

  return {
    page_number: evidence.page_number,
    bbox: evidence.bbox,
    normalized,
  };
}

export function mapAlertSeverityToPdfSeverity(
  severity: ProjectAlert["severity"],
): PdfHighlight["severity"] {
  switch (String(severity).toLowerCase()) {
    case "critical":
      return "critical";
    case "high":
      return "high";
    case "medium":
      return "medium";
    default:
      return "low";
  }
}

export function buildDocumentDownloadUrl(documentId: string): string {
  return `${env.API_BASE_URL}/documents/${documentId}/download`;
}
