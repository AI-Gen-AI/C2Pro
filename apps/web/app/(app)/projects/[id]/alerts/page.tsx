/**
 * Test Suite ID: TASK-1347
 * Route Coverage: Project alerts page uses generated backend alerts client
 */
"use client";

import { useParams } from "next/navigation";
import { useMemo } from "react";
import { AlertReviewCenter, type ReviewAlert } from "@/components/features/alerts/AlertReviewCenter";
import { useListProjectAlertsApiV1ProjectsProjectIdAlertsGet } from "@/lib/api/generated/alerts/alerts";

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

function mapAlertToReviewAlert(alert: {
  id: string;
  category: string;
  severity: string;
  status: string;
  message: string;
}): ReviewAlert {
  return {
    id: alert.id,
    title: alert.message,
    severity: SEVERITY_MAP[alert.severity] ?? "medium",
    status: STATUS_MAP[alert.status] ?? "pending",
  };
}

export default function AlertsPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { data, isLoading, error } =
    useListProjectAlertsApiV1ProjectsProjectIdAlertsGet(id, undefined);

  const alerts = useMemo(() => 
    (data?.items ?? []).map(mapAlertToReviewAlert),
    [data?.items]
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
      <AlertReviewCenter projectId={id} alerts={alerts} />
    </div>
  );
}

