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
 * Map backend DocumentType to frontend type
 */
const documentTypeMap: Record<string, DocumentInfo['type']> = {
  contract: 'contract',
  schedule: 'schedule',
  budget: 'budget',
  specification: 'specification',
  drawing: 'drawing',
  other: 'other',
};

/**
 * Transform backend DocumentResponse to frontend DocumentInfo
 */
function transformDocument(doc: DocumentListResponse): DocumentInfo {
  // Map file format to extension based on filename
  const extension = doc.filename?.split('.').pop()?.toLowerCase() || 'pdf';
  const validExtension = ['pdf', 'xlsx', 'docx', 'dwg'].includes(extension)
    ? extension as DocumentInfo['extension']
    : 'pdf';

  // Map document type (if provided in response, otherwise default)
  const backendType = doc.document_type?.toLowerCase();
  const mappedType = backendType ? documentTypeMap[backendType] || 'other' : 'other';

  return {
    id: doc.id,
    name: doc.filename || 'Untitled',
    type: mappedType,
    extension: validExtension,
    url: '',
    totalPages: undefined,
    fileSize: doc.file_size_bytes || 0,
    uploadedAt: doc.uploaded_at ? new Date(doc.uploaded_at) : undefined,
    status: doc.status,
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
