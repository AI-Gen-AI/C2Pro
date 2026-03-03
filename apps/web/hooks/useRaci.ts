/**
 * useRaci Hook
 * Fetches RACI matrix data from the backend
 */

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api/client';

export interface RaciRow {
  activity: string;
  projectManager: string;
  technicalLead: string;
  stakeholder: string;
  contractor: string;
}

interface UseRaciResult {
  data: RaciRow[];
  loading: boolean;
  error: Error | null;
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
        const url = projectId
          ? `/projects/${projectId}/raci`
          : '/raci';
        const response = await apiClient.get<RaciRow[]>(url);
        if (active) setData(response.data);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err : new Error('Failed to fetch RACI data'));
      } finally {
        if (active) setLoading(false);
      }
    }

    fetchRaci();
    return () => { active = false; };
  }, [projectId]);

  return { data, loading, error };
}
