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
 *
 * Codex P2 (PR #1059, exact HEAD 6f68051): the previous version initialized
 * `loading` to `false` and refetched in a plain `useEffect([projectId])`, so (a)
 * the very first render could report "0 alerts" before any request had even
 * started, and (b) nothing stopped a late response for a superseded `projectId`
 * from overwriting state set by a newer request (classic fetch race). Fixed by
 * tagging every state snapshot with the `projectId` it belongs to and deriving
 * the returned `alerts`/`loading`/`error` against the *current* `projectId` prop
 * -- not the state variable's own timing -- plus an incrementing request id so a
 * stale response (success or failure) for an old `projectId` is dropped outright.
 */

import { useState, useEffect, useRef, useCallback } from "react";
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

interface AlertsSnapshot {
  /** The project this snapshot's alerts/error actually belong to. */
  projectId: string | null;
  alerts: ReviewAlert[];
  loading: boolean;
  error: Error | null;
}

const INITIAL_SNAPSHOT: AlertsSnapshot = {
  projectId: null,
  alerts: [],
  loading: false,
  error: null,
};

export function useProjectAlerts(
  projectId: string | null,
): UseProjectAlertsResult {
  const [snapshot, setSnapshot] = useState<AlertsSnapshot>(INITIAL_SNAPSHOT);
  // Monotonic token: only the response for the most recently started request is
  // ever allowed to write state, so a late A-response can never overwrite B.
  const latestRequestRef = useRef(0);

  const fetchAlerts = useCallback(async () => {
    const requestId = ++latestRequestRef.current;

    if (!projectId) {
      setSnapshot({ projectId: null, alerts: [], loading: false, error: null });
      return;
    }

    setSnapshot((prev) => ({
      projectId,
      // Never show project A's rows under project B while B is loading.
      alerts: prev.projectId === projectId ? prev.alerts : [],
      loading: true,
      error: null,
    }));

    try {
      const response = await apiClient.get<AlertListResponse>(
        `/alerts/projects/${projectId}`,
      );
      if (requestId !== latestRequestRef.current) return; // superseded by a newer request
      setSnapshot({
        projectId,
        alerts: response.data.items.map(transformAlert),
        loading: false,
        error: null,
      });
    } catch (err) {
      if (requestId !== latestRequestRef.current) return; // superseded by a newer request
      const error =
        err instanceof Error ? err : new Error("Failed to fetch alerts");
      console.error("Error fetching project alerts:", err);
      setSnapshot({ projectId, alerts: [], loading: false, error });
    }
  }, [projectId]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  // Derived, not read straight off state: if `projectId` changed but the effect
  // above has not committed its reset yet, `snapshot.projectId` is still the old
  // one -- so compute output against the *current* prop instead of trusting the
  // state variable's own timing. This is what actually prevents a one-render
  // flash of project A's alerts/count while the page already says project B.
  const belongsToCurrentProject = snapshot.projectId === projectId;
  return {
    alerts: belongsToCurrentProject ? snapshot.alerts : [],
    loading: !projectId ? false : !belongsToCurrentProject || snapshot.loading,
    error: belongsToCurrentProject ? snapshot.error : null,
    refetch: fetchAlerts,
  };
}
