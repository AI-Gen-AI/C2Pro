/**
 * useDocumentRelationshipExplanation Hook
 * Fetches a backend-generated, citation-grounded explanation for a document.
 */

import { useEffect, useState } from "react";
import {
  getDocumentRelationshipExplanation,
  type DocumentRelationshipExplanation,
} from "@/lib/api";

interface UseDocumentRelationshipExplanationResult {
  explanation: DocumentRelationshipExplanation | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useDocumentRelationshipExplanation(
  documentId: string | null,
): UseDocumentRelationshipExplanationResult {
  const [explanation, setExplanation] =
    useState<DocumentRelationshipExplanation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchExplanation = async () => {
    if (!documentId) {
      setExplanation(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const fetchedExplanation = await getDocumentRelationshipExplanation(documentId);
      setExplanation(fetchedExplanation);
    } catch (err) {
      const nextError =
        err instanceof Error
          ? err
          : new Error("Failed to fetch document relationship explanation");
      setError(nextError);
      console.error("Error fetching document relationship explanation:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExplanation();
  }, [documentId]);

  return {
    explanation,
    loading,
    error,
    refetch: fetchExplanation,
  };
}
