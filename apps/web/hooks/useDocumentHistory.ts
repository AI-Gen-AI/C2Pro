/**
 * useDocumentHistory Hook
 * Fetches persisted timeline events for a document.
 */

import { useEffect, useState } from "react";
import {
  getDocumentHistory,
  type EvidenceHistoryEvent,
} from "@/lib/api";

interface UseDocumentHistoryResult {
  items: EvidenceHistoryEvent[];
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useDocumentHistory(
  documentId: string | null,
): UseDocumentHistoryResult {
  const [items, setItems] = useState<EvidenceHistoryEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchHistory = async () => {
    if (!documentId) {
      setItems([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const fetchedHistory = await getDocumentHistory(documentId);
      setItems(fetchedHistory);
    } catch (err) {
      const nextError =
        err instanceof Error ? err : new Error("Failed to fetch document history");
      setError(nextError);
      console.error("Error fetching document history:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [documentId]);

  return {
    items,
    loading,
    error,
    refetch: fetchHistory,
  };
}
