/**
 * useProjectAlerts Hook
 * Fetches project alerts from the backend and maps them to ReviewAlert shape.
 *
 * PC-7b (#672, board #1049): verified route wiring against
 * `apps/api/src/alerts/adapters/http/router.py` -- the served, real endpoint is
 * `GET /alerts/projects/{project_id}` (`src.alerts.application.dtos.AlertResponse`,
 * via `src.alerts.application.dtos.AlertListResponse`), not the never-registered
 * `Page[AlertRead]` router in `analysis/adapters/http/alerts_router.py` (dead code,
 * not imported by `main.py`) and not a hand-invented path. That served response has
 * no offset/limit pagination -- `total` is always `len(items)` -- so this hook never
 * implies more alerts exist than were fetched.
 *
 * `clauseId` used to be fabricated as `clause-${alert.id}` regardless of whether the
 * backend actually resolved a source clause. It now mirrors the same real-evidence
 * mapping already reviewed in `app/(app)/projects/[id]/alerts/page.tsx`: the
 * persisted `source_clause_id` first, then the detector's `detection_evidence`
 * clause/document as a fallback, and nothing when neither exists.
 */

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api/client";
import type { ReviewAlert } from "@/components/features/alerts/AlertReviewCenter";

interface UseProjectAlertsResult {
  alerts: ReviewAlert[];
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

interface DetectionEvidenceResponse {
  source_clause_id?: string | null;
  source_document_id?: string | null;
}

interface AlertResponse {
  id: string;
  project_id: string;
  category: string;
  severity: string;
  status: string;
  message: string;
  /** Real, persisted source clause -- never fabricated. */
  source_clause_id?: string | null;
  detection_evidence?: DetectionEvidenceResponse | null;
}

interface AlertListResponse {
  items: AlertResponse[];
  total: number;
}

const SEVERITY_MAP: Record<string, ReviewAlert["severity"]> = {
  critical: "critical",
  high: "high",
  medium: "medium",
  low: "low",
};

const STATUS_MAP: Record<string, ReviewAlert["status"]> = {
  open: "pending",
  resolved: "approved",
  rejected: "rejected",
};

const ASSIGNEE_MAP: Record<string, string> = {
  LEGAL: "legal.reviewer",
  BUDGET: "finance.analyst",
  TECHNICAL: "tech.lead",
  TIME: "scheduler",
  SCOPE: "project.manager",
  QUALITY: "qa.manager",
};

function transformAlert(alert: AlertResponse): ReviewAlert {
  // Never invent a clause id: only a real, resolved source clause (persisted, or
  // from the detector's own evidence) is ever shown or linked.
  const persistedClauseId = alert.source_clause_id ?? undefined;
  const clauseId = persistedClauseId ?? alert.detection_evidence?.source_clause_id ?? undefined;
  const sourceDocumentId = alert.detection_evidence?.source_document_id ?? undefined;

  return {
    id: alert.id,
    title: alert.message,
    severity: SEVERITY_MAP[alert.severity] ?? "medium",
    status: STATUS_MAP[alert.status] ?? "pending",
    assignee: ASSIGNEE_MAP[alert.category] ?? "project.manager",
    ...(clauseId ? { clauseId } : {}),
    ...(persistedClauseId && sourceDocumentId
      ? { addressableClauseId: persistedClauseId, sourceDocumentId }
      : {}),
  };
}

export function useProjectAlerts(
  projectId: string | null,
): UseProjectAlertsResult {
  const [alerts, setAlerts] = useState<ReviewAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchAlerts = async () => {
    if (!projectId) {
      setAlerts([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.get<AlertListResponse>(
        `/alerts/projects/${projectId}`,
      );
      setAlerts(response.data.items.map(transformAlert));
    } catch (err) {
      const error =
        err instanceof Error ? err : new Error("Failed to fetch alerts");
      setError(error);
      console.error("Error fetching project alerts:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [projectId]);

  return { alerts, loading, error, refetch: fetchAlerts };
}
