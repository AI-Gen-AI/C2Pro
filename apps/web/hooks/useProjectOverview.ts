/**
 * useProjectOverview Hook
 * Fetches project overview stats (coherence, alerts, documents, budget)
 */

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api/client";

export interface ProjectOverviewStats {
  coherenceScore: number;
  openAlerts: number;
  documentCount: number;
  budgetUsed: number;
  recentAlerts: { severity: string; title: string }[];
}

interface CoherenceDashboard {
  coherence_score: number;
  alert_count: number;
  document_count: number;
  sub_scores: Record<string, number>;
}

interface AlertResponse {
  id: string;
  severity: string;
  status: string;
  message: string;
}

interface AlertListResponse {
  items: AlertResponse[];
  total: number;
}

interface UseProjectOverviewResult {
  stats: ProjectOverviewStats | null;
  loading: boolean;
  error: Error | null;
}

export function useProjectOverview(
  projectId: string,
): UseProjectOverviewResult {
  const [stats, setStats] = useState<ProjectOverviewStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let active = true;

    async function fetchOverview() {
      setLoading(true);
      setError(null);

      try {
        const [dashboardRes, alertsRes] = await Promise.all([
          apiClient.get<CoherenceDashboard>(
            `/coherence/dashboard/${projectId}`,
          ),
          apiClient.get<AlertListResponse>(`/projects/${projectId}/alerts`),
        ]);

        if (!active) return;

        const dashboard = dashboardRes.data;
        const alerts = alertsRes.data.items;

        const openAlerts = alerts.filter((a) => a.status === "open");
        const subScores =
          dashboard.sub_scores && typeof dashboard.sub_scores === "object"
            ? (dashboard.sub_scores as Record<string, number>)
            : {};
        const budgetScore = subScores["BUDGET"] ?? 0;

        setStats({
          coherenceScore: dashboard.coherence_score,
          openAlerts: openAlerts.length,
          documentCount: dashboard.document_count,
          budgetUsed: 100 - budgetScore,
          recentAlerts: openAlerts.slice(0, 3).map((a) => ({
            severity: a.severity,
            title: a.message.split(" — ")[0],
          })),
        });
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof Error
            ? err
            : new Error("Failed to fetch project overview"),
        );
      } finally {
        if (active) setLoading(false);
      }
    }

    fetchOverview();
    return () => {
      active = false;
    };
  }, [projectId]);

  return { stats, loading, error };
}
