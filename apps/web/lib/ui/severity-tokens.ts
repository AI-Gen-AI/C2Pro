/**
 * Canonical Design System Token Maps — TASK-FRT-194
 *
 * Provides a single consolidated source of truth for severity and status
 * to Tailwind CSS color/badge style mappings.
 */

export type SeverityKey = "critical" | "high" | "medium" | "low" | string;

/**
 * Maps standard severity levels to Tailwind CSS badge class names.
 */
export function severityToToken(severity: SeverityKey): string {
  const s = severity.toLowerCase().trim();
  switch (s) {
    case "critical":
      return "bg-red-100 text-red-800 border-red-200";
    case "high":
      return "bg-orange-100 text-orange-800 border-orange-200";
    case "medium":
      return "bg-yellow-100 text-yellow-800 border-yellow-200";
    case "low":
      return "bg-green-100 text-green-800 border-green-200";
    default:
      return "bg-gray-100 text-gray-800 border-gray-200";
  }
}

/**
 * Maps standard statuses to Tailwind CSS badge class names.
 */
export function statusToToken(status: string): string {
  const s = status.toLowerCase().trim();
  switch (s) {
    // Green tones: parsed, analyzed, approved, resolved, success, active, completed
    case "parsed":
    case "analyzed":
    case "approved":
    case "resolved":
    case "success":
    case "active":
    case "completed":
      return "bg-green-100 text-green-700 border-green-200";

    // Red tones: rejected, error, failed, conflicting_evidence
    case "rejected":
    case "error":
    case "failed":
    case "conflicting_evidence":
      return "bg-red-100 text-red-700 border-red-200";

    // Orange tones: escalated, processing_error
    case "escalated":
    case "processing_error":
      return "bg-orange-100 text-orange-700 border-orange-200";

    // Yellow/Amber tones: warning, pending_review_required, pending_review_conditional
    case "warning":
    case "pending_review_required":
    case "pending_review_conditional":
      return "bg-yellow-100 text-yellow-700 border-yellow-200";

    // Blue tones: processing, in progress, in_progress, pending_documents
    case "processing":
    case "in progress":
    case "in_progress":
    case "pending_documents":
      return "bg-blue-100 text-blue-700 border-blue-200";

    // Special dark badge: open, pending
    case "open":
    case "pending":
      return "bg-slate-900 text-white border-slate-900";

    // Gray tones: queued, uploaded, closed, dismissed, not_applicable, insufficient_evidence, inactive, default
    case "queued":
    case "uploaded":
    case "closed":
    case "dismissed":
    case "not_applicable":
    case "insufficient_evidence":
    case "inactive":
    default:
      return "bg-gray-100 text-gray-700 border-gray-200";
  }
}
