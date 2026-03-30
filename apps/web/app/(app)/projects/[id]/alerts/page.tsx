/**
 * Test Suite ID: TASK-1347
 * Route Coverage: Project alerts page uses generated backend alerts client
 */
"use client";

import { useParams } from "next/navigation";
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

const ASSIGNEE_MAP: Record<string, string> = {
  LEGAL: "legal.reviewer",
  BUDGET: "finance.analyst",
  TECHNICAL: "tech.lead",
  TIME: "scheduler",
  SCOPE: "project.manager",
  QUALITY: "qa.manager",
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
    clauseId: `clause-${alert.id}`,
    assignee: ASSIGNEE_MAP[alert.category] ?? "project.manager",
  };
}

export default function AlertsPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { data, isLoading, error } =
    useListProjectAlertsApiV1ProjectsProjectIdAlertsGet(id, undefined);

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

  const alerts = (data?.items ?? []).map(mapAlertToReviewAlert);

  return (
    <div className="space-y-6">
      <AlertReviewCenter projectId={id} alerts={alerts} />
    </div>
  );
}
