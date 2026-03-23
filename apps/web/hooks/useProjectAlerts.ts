/**
 * useProjectAlerts Hook
 * Fetches project alerts from the backend and maps them to ReviewAlert shape
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

interface AlertResponse {
  id: string;
  projectId: string;
  category: string;
  severity: string;
  status: string;
  message: string;
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
  return {
    id: alert.id,
    title: alert.message,
    severity: SEVERITY_MAP[alert.severity] ?? "medium",
    status: STATUS_MAP[alert.status] ?? "pending",
    clauseId: `clause-${alert.id}`,
    assignee: ASSIGNEE_MAP[alert.category] ?? "project.manager",
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
        `/projects/${projectId}/alerts`,
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
