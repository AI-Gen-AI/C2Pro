/**
 * useDocumentEntities Hook
 * Fetches and manages document entities from the backend
 */

import { useState, useEffect } from 'react';
import {
  getDocumentEntities,
  createHighlightsFromEntities,
  type ProcessedEntity,
} from '@/lib/api';
import type { Highlight } from '@/types/highlight';

interface UseDocumentEntitiesResult {
  entities: ProcessedEntity[];
  highlights: Highlight[];
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch entities for a specific document
 */
export function useDocumentEntities(
  documentId: string | null,
  pageHeight?: number
): UseDocumentEntitiesResult {
  const [entities, setEntities] = useState<ProcessedEntity[]>([]);
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchEntities = async () => {
    if (!documentId) {
      setEntities([]);
      setHighlights([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const fetchedEntities = await getDocumentEntities(documentId, pageHeight);
      setEntities(fetchedEntities);

      const generatedHighlights = createHighlightsFromEntities(fetchedEntities);
      setHighlights(generatedHighlights);
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to fetch entities');
      setError(error);
      console.error('Error fetching document entities:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEntities();
  }, [documentId, pageHeight]);

  return {
    entities,
    highlights,
    loading,
    error,
    refetch: fetchEntities,
  };
}
