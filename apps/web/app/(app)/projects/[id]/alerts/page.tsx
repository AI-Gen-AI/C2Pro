/**
 * Test Suite ID: TASK-1347
 * Route Coverage: Project alerts page uses generated backend alerts client
 */
"use client";

import { useParams } from "next/navigation";
import { useCallback, useMemo } from "react";
import { AlertReviewCenter, type ReviewAlert } from "@/components/features/alerts/AlertReviewCenter";
import {
  getListProjectAlertsApiV1AlertsProjectsProjectIdGetQueryKey,
  reviewAlertApiV1AlertsAlertIdReviewPost,
  resolveAlertApiV1AlertsAlertIdResolvePost,
  useListProjectAlertsApiV1AlertsProjectsProjectIdGet,
} from "@/lib/api/generated/alerts/alerts";
import { getGetCoherenceDashboardApiCoherenceDashboardProjectIdGetQueryKey } from "@/lib/api/generated/coherence-dashboard/coherence-dashboard";
import { useQueryClient } from "@tanstack/react-query";

const SEVERITY_MAP: Record<string, ReviewAlert["severity"]> = {
  critical: "critical",
  high: "high",
  medium: "medium",
  low: "low",
};

const STATUS_MAP: Record<string, ReviewAlert["status"]> = {
  open: "pending",
  acknowledged: "approved",
  resolved: "approved",
  dismissed: "rejected",
  rejected: "rejected",
};

function mapAlertToReviewAlert(alert: {
  id: string;
  category: string;
  severity: string;
  status: string;
  message: string;
  source_clause_id?: string | null;
  detection_evidence?: {
    source_clause_id?: string | null;
    source_document_id?: string | null;
    claim?: string | null;
    quote?: string | null;
  } | null;
}): ReviewAlert {
  const persistedClauseId = alert.source_clause_id ?? undefined;
  const clauseId =
    persistedClauseId ?? alert.detection_evidence?.source_clause_id ?? undefined;
  const sourceDocumentId =
    alert.detection_evidence?.source_document_id ?? undefined;

  return {
    id: alert.id,
    title: alert.message,
    severity: SEVERITY_MAP[alert.severity] ?? "medium",
    status: STATUS_MAP[alert.status] ?? "pending",
    ...(clauseId ? { clauseId } : {}),
    ...(persistedClauseId && sourceDocumentId
      ? { addressableClauseId: persistedClauseId, sourceDocumentId }
      : {}),
    ...(alert.detection_evidence?.claim
      ? { evidenceClaim: alert.detection_evidence.claim }
      : {}),
    ...(alert.detection_evidence?.quote
      ? { evidenceQuote: alert.detection_evidence.quote }
      : {}),
  };
}

export default function AlertsPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const queryClient = useQueryClient();
  const { data, isLoading, error } =
    useListProjectAlertsApiV1AlertsProjectsProjectIdGet(id, undefined);

  const alerts = useMemo(() => 
    (data?.items ?? []).map(mapAlertToReviewAlert),
    [data?.items]
  );

  const refreshProjectState = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: getListProjectAlertsApiV1AlertsProjectsProjectIdGetQueryKey(id),
      }),
      queryClient.invalidateQueries({
        queryKey: getGetCoherenceDashboardApiCoherenceDashboardProjectIdGetQueryKey(id),
      }),
    ]);
  }, [id, queryClient]);

  const approveAlert = useCallback(
    async (alertId: string) => {
      await reviewAlertApiV1AlertsAlertIdReviewPost(alertId, {
        decision: "approve",
        comment: "",
      });
      await refreshProjectState();
    },
    [refreshProjectState],
  );

  const rejectAlert = useCallback(
    async (alertId: string, reason: string) => {
      await reviewAlertApiV1AlertsAlertIdReviewPost(alertId, {
        decision: "reject",
        comment: reason,
      });
      await refreshProjectState();
    },
    [refreshProjectState],
  );

  const resolveAlert = useCallback(
    async (alertId: string, resolution: string, rootCause?: string) => {
      await resolveAlertApiV1AlertsAlertIdResolvePost(alertId, {
        resolution,
        root_cause: rootCause ?? null,
      });
      await refreshProjectState();
    },
    [refreshProjectState],
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        Loading alerts…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-24 text-destructive">
        {error instanceof Error ? error.message : "Failed to load alerts"}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <AlertReviewCenter
        projectId={id}
        alerts={alerts}
        onApprove={approveAlert}
        onReject={rejectAlert}
        onResolve={resolveAlert}
      />
    </div>
  );
}

