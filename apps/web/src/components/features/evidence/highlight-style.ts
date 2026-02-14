/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
import type { EvidenceSeverity } from "@/src/components/features/evidence/highlight-mapper";

type ValidationStatus = "pending" | "approved" | "rejected";

export interface HighlightStyleInput {
  severity: EvidenceSeverity;
  validationStatus: ValidationStatus;
  isActive: boolean;
}

const severityClass: Record<EvidenceSeverity, string> = {
  critical: "severity-critical",
  high: "severity-high",
  medium: "severity-medium",
  low: "severity-low",
};

const validationClass: Record<ValidationStatus, string> = {
  pending: "status-pending",
  approved: "approved",
  rejected: "rejected",
};

export function resolveHighlightStyle(input: HighlightStyleInput): {
  className: string;
} {
  const parts = [
    "highlight-chip",
    severityClass[input.severity],
    validationClass[input.validationStatus],
  ];

  if (input.isActive) {
    parts.push("ring");
  }

  return { className: parts.join(" ") };
}
