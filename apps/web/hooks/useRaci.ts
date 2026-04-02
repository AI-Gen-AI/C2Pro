/**
 * useRaci Hook
 * Fetches RACI matrix data from the backend
 */

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api/client";

export interface RaciRow {
  activity: string;
  projectManager: string;
  technicalLead: string;
  stakeholder: string;
  contractor: string;
  sequenceIndex?: number;
  taskCode?: string;
  plannedStart?: string | null;
  plannedEnd?: string | null;
  projectId?: string;
}

interface RaciAssignment {
  stakeholder_id: string;
  stakeholder_name: string | null;
  role: string;
  is_verified: boolean;
}

interface RaciTaskRow {
  task_id: string;
  task_code: string;
  task_name: string;
  sequence_index: number;
  planned_start?: string | null;
  planned_end?: string | null;
  assignments: RaciAssignment[];
}

interface RaciMatrixResponse {
  matrix: RaciTaskRow[];
}

interface UseRaciResult {
  data: RaciRow[];
  loading: boolean;
  error: Error | null;
}

function _transformMatrixToRows(
  matrix: RaciTaskRow[],
  projectId?: string,
): RaciRow[] {
  return matrix.map((row) => {
    const byRole: Record<string, string> = {};
    for (const assignment of row.assignments) {
      const name = assignment.stakeholder_name ?? assignment.role;
      byRole[assignment.role.toUpperCase()] = name;
    }
    return {
      activity: row.task_name,
      projectManager: byRole["RESPONSIBLE"] ?? byRole["ACCOUNTABLE"] ?? "",
      technicalLead: byRole["ACCOUNTABLE"] ?? "",
      stakeholder: byRole["CONSULTED"] ?? "",
      contractor: byRole["INFORMED"] ?? "",
      sequenceIndex: row.sequence_index,
      taskCode: row.task_code,
      plannedStart: row.planned_start ?? null,
      plannedEnd: row.planned_end ?? null,
      projectId,
    };
  });
}

export function useRaci(projectId?: string): UseRaciResult {
  const [data, setData] = useState<RaciRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let active = true;

    async function fetchRaci() {
      setLoading(true);
      setError(null);

      try {
        const url = projectId ? `/projects/${projectId}/raci` : "/raci";
        const response = await apiClient.get<RaciMatrixResponse>(url);
        if (active) {
          setData(
            _transformMatrixToRows(response.data.matrix ?? [], projectId),
          );
        }
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof Error ? err : new Error("Failed to fetch RACI data"),
        );
      } finally {
        if (active) setLoading(false);
      }
    }

    fetchRaci();
    return () => {
      active = false;
    };
  }, [projectId]);

  return { data, loading, error };
}
