/**
 * useAlerts Hook
 * Fetches all alerts across projects from the backend
 */

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api/client";

export interface AlertListItem {
  id: string;
  severity: string;
  type: string;
  title: string;
  description: string;
  project: string;
  status: string;
  created_at?: string;
  sla_due_at?: string | null;
  sla_policy_name?: string | null;
}

interface AlertResponse {
  id: string;
  project_id: string;
  category: string;
  severity: string;
  status: string;
  message: string;
  created_at?: string;
  sla_due_at?: string | null;
  sla_policy_name?: string | null;
}

interface AlertListResponse {
  items: AlertResponse[];
  total: number;
}

interface ProjectResponse {
  id: string;
  name: string;
}

interface ProjectsListResponse {
  items: ProjectResponse[];
}

const STATUS_MAP: Record<string, string> = {
  open: "Open",
  resolved: "Resolved",
  rejected: "Rejected",
};

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

interface UseAlertsResult {
  alerts: AlertListItem[];
  loading: boolean;
  error: Error | null;
}

export function useAlerts(): UseAlertsResult {
  const [alerts, setAlerts] = useState<AlertListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let active = true;

    async function fetchAlerts() {
      setLoading(true);
      setError(null);

      try {
        const [alertsRes, projectsRes] = await Promise.all([
          apiClient.get<AlertListResponse>("/alerts"),
          apiClient.get<ProjectsListResponse>("/projects"),
        ]);

        if (!active) return;

        const projectMap = new Map(
          projectsRes.data.items.map((p: ProjectResponse) => [p.id, p.name]),
        );

        const mapped = alertsRes.data.items.map((a: AlertResponse) => ({
          id: a.id,
          severity: capitalize(a.severity),
          type: capitalize(a.category),
          title: a.message.split(" — ")[0],
          description: a.message.split(" — ")[1] ?? a.message,
          project: projectMap.get(a.project_id) ?? a.project_id,
          status: STATUS_MAP[a.status] ?? capitalize(a.status),
          created_at: a.created_at,
          sla_due_at: a.sla_due_at ?? null,
          sla_policy_name: a.sla_policy_name ?? null,
        }));

        setAlerts(mapped);
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof Error ? err : new Error("Failed to fetch alerts"),
        );
      } finally {
        if (active) setLoading(false);
      }
    }

    fetchAlerts();
    return () => {
      active = false;
    };
  }, []);

  return { alerts, loading, error };
}
