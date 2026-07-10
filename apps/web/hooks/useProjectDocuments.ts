/**
 * useProjectDocuments Hook
 * Fetches and manages project documents from the backend
 */

import { useQuery } from '@tanstack/react-query';
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

function hasInFlightDocs(documents: DocumentInfo[] | undefined): boolean {
  return (documents ?? []).some((doc) =>
    ['uploaded', 'queued', 'processing'].includes(
      String(doc.status ?? '').toLowerCase(),
    ),
  );
}

/**
 * Hook to fetch documents for a specific project
 */
export function useProjectDocuments(projectId: string | null): UseProjectDocumentsResult {
  const documentsQuery = useQuery({
    queryKey: ['project-documents', projectId],
    enabled: Boolean(projectId),
    queryFn: async () => {
      if (!projectId) {
        return [];
      }

      const fetchedDocs = await getProjectDocuments(projectId);
      return fetchedDocs.map(transformDocument);
    },
    refetchInterval: (query) =>
      hasInFlightDocs(query.state.data) ? 5000 : false,
  });

  const error =
    documentsQuery.error instanceof Error
      ? documentsQuery.error
      : documentsQuery.error
        ? new Error('Failed to fetch documents')
        : null;

  return {
    documents: documentsQuery.data ?? [],
    loading: documentsQuery.isLoading,
    error,
    refetch: async () => {
      await documentsQuery.refetch();
    },
  };
}
