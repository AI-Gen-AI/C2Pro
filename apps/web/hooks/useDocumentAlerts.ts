/**
 * useDocumentAlerts Hook
 * Fetches alerts for a document and maps them into highlights
 */

import { useEffect, useState } from 'react';
import {
  createHighlightsFromAlerts,
  getDocumentAlerts,
} from '@/lib/api';
import type { AlertResponse } from '@/types/backend';
import type { Highlight } from '@/types/highlight';

interface UseDocumentAlertsResult {
  alerts: AlertResponse[];
  highlights: Highlight[];
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useDocumentAlerts(documentId: string | null): UseDocumentAlertsResult {
  const [alerts, setAlerts] = useState<AlertResponse[]>([]);
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchAlerts = async () => {
    if (!documentId) {
      setAlerts([]);
      setHighlights([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const fetchedAlerts = await getDocumentAlerts(documentId);
      setAlerts(fetchedAlerts);
      setHighlights(createHighlightsFromAlerts(fetchedAlerts));
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to fetch alerts');
      setError(error);
      console.error('Error fetching alerts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [documentId]);

  return {
    alerts,
    highlights,
    loading,
    error,
    refetch: fetchAlerts,
  };
}
