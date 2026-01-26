/**
 * useProjectDocuments Hook
 * Fetches and manages project documents from the backend
 */

import { useState, useEffect } from 'react';
import { getProjectDocuments } from '@/lib/api';
import type { DocumentListResponse } from '@/types/backend';
import type { DocumentInfo } from '@/types/document';

interface UseProjectDocumentsResult {
  documents: DocumentInfo[];
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Transform backend DocumentResponse to frontend DocumentInfo
 */
function transformDocument(doc: DocumentListResponse): DocumentInfo {
  // Map backend DocumentType to frontend type
  const typeMap: Record<string, any> = {
    CONTRACT: 'contract',
    SCHEDULE: 'schedule',
    BOM: 'bom',
    SPECIFICATION: 'specification',
    DRAWING: 'drawing',
    OTHER: 'contract',
  };

  // Map file format to extension
  const extension = 'pdf';

  return {
    id: doc.id,
    name: doc.filename || 'Untitled',
    type: 'contract',
    extension,
    url: '',
    totalPages: undefined,
    fileSize: doc.file_size_bytes || 0,
    uploadedAt: doc.uploaded_at ? new Date(doc.uploaded_at) : undefined,
  };
}

/**
 * Hook to fetch documents for a specific project
 */
export function useProjectDocuments(projectId: string | null): UseProjectDocumentsResult {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchDocuments = async () => {
    if (!projectId) {
      setDocuments([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const fetchedDocs = await getProjectDocuments(projectId);
      const transformed = fetchedDocs.map(transformDocument);
      setDocuments(transformed);
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to fetch documents');
      setError(error);
      console.error('Error fetching project documents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [projectId]);

  return {
    documents,
    loading,
    error,
    refetch: fetchDocuments,
  };
}
